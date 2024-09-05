import bpy

import os.path

from typing import TypedDict, Required, NotRequired, Iterable, TypeVar

import strictyaml
from strictyaml import (
    Str,
    Int,
    Float,
    Bool,
    Seq,
    Map,
    MapPattern,
    MapCombined,
    Optional,
    CommaSeparated,
)

node_link = Map(
    {
        "node": Str(),
        Optional("socket"): Int() | Str(),
        Optional("muted", default=False): Bool(),
    }
)


class NodeLink(TypedDict, total=False):
    node: Required[str]
    socket: int | str
    muted: bool


scalar = Int() | Float() | Bool() | CommaSeparated(Float()) | Str()
node_input = node_link | scalar
NodeInput = NodeLink | int | float | bool | list[float] | str

node_definition = MapCombined(
    {
        "type": Str(),
        Optional("inputs"): MapPattern(Str(), node_input) | Seq(node_input),
    },
    Str(),
    scalar,
)


class NodeDefinition(TypedDict, total=False):
    type: Required[str]
    inputs: dict[str, NodeInput] | list[NodeInput]


node_tree = MapPattern(Str(), node_definition)
NodeTreeDefinition = dict[str, NodeDefinition]

node_group = Map(
    {
        Optional("inputs"): MapPattern(Str(), Str()),
        Optional("outputs"): MapPattern(Str(), Str()),
        "nodes": node_tree,
    }
)


class NodeGroupDefinition(TypedDict, total=False):
    inputs: dict[str, str]
    outputs: dict[str, str]
    nodes: Required[NodeTreeDefinition]


_parsed_file_cache: dict[str, NodeTreeDefinition | NodeGroupDefinition] = {}


def _load_file(
    filepath: str, schema: strictyaml.Validator
) -> NodeTreeDefinition | NodeGroupDefinition:
    if existing := _parsed_file_cache.get(filepath):
        return existing

    with open(filepath) as f:
        yaml = f.read()

    parsed = strictyaml.load(yaml, schema, label=filepath).data
    _parsed_file_cache[filepath] = parsed
    return parsed


def load_material(filepath: str, name: str) -> bpy.types.Material:
    doc: NodeTreeDefinition = _load_file(filepath, node_tree)  # type: ignore[assignment]

    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.node_tree.nodes.clear()
    _populate_node_tree(material.node_tree, doc)
    return material


T = TypeVar("T", bound=bpy.types.NodeTree)


def load_node_group(filepath: str, name: str, tree_type: type[T]) -> T:
    doc: NodeGroupDefinition = _load_file(filepath, node_group)  # type: ignore[assignment]

    group = bpy.data.node_groups.new(name, tree_type.__name__)
    assert isinstance(group, tree_type)

    for input_name, socket_type in doc.get("inputs", {}).items():
        group.interface.new_socket(input_name, in_out="INPUT", socket_type=socket_type)

    for output_name, socket_type in doc.get("outputs", {}).items():
        group.interface.new_socket(
            output_name, in_out="OUTPUT", socket_type=socket_type
        )

    _populate_node_tree(group, doc["nodes"])
    return group


def load_shader_node_group(filepath: str, name: str) -> bpy.types.ShaderNodeTree:
    return load_node_group(filepath, name, bpy.types.ShaderNodeTree)


def load_geometry_node_group(filepath: str, name: str) -> bpy.types.GeometryNodeTree:
    return load_node_group(filepath, name, bpy.types.GeometryNodeTree)


def _populate_node_tree(
    tree: bpy.types.NodeTree,
    definitions: dict[str, NodeDefinition],
) -> None:
    # create nodes
    for name, definition in definitions.items():
        node = tree.nodes.new(definition["type"])
        node.name = name

        for property, value in definition.items():
            if property == "node_tree":
                assert isinstance(
                    node, bpy.types.ShaderNodeGroup | bpy.types.GeometryNodeGroup
                )
                node.node_tree = bpy.data.node_groups[value]
            elif property not in ("type", "inputs"):
                setattr(node, property, value)

    # set up inputs after all nodes have been created,
    # so that nodes can be defined in any order
    for name, definition in definitions.items():
        if inputs := definition.get("inputs"):
            _setup_inputs(tree, name, inputs)


def _setup_inputs(
    tree: bpy.types.NodeTree,
    node_name: str,
    inputs: dict[str, NodeInput] | list[NodeInput],
) -> None:
    iter: Iterable[tuple[str | int, NodeInput]]
    if isinstance(inputs, list):
        iter = enumerate(inputs)
    elif isinstance(inputs, dict):
        iter = inputs.items()

    node = tree.nodes[node_name]

    for key, input in iter:
        dst_socket = node.inputs[key]
        assert dst_socket.enabled, f"{dst_socket!r} is not enabled"

        if not isinstance(input, dict):
            if isinstance(input, str) and not isinstance(
                dst_socket, bpy.types.NodeSocketString
            ):
                input = {"node": input}  # shorthand for the default-socket case
            else:
                dst_socket.default_value = input
                continue

        src_node = tree.nodes[input["node"]]
        if "socket" in input:
            src_socket = src_node.outputs[input["socket"]]
            assert src_socket.enabled, f"{src_socket!r} is not enabled"
        else:
            # find the "default (first) output"
            src_socket = next(s for s in src_node.outputs if s.enabled)

        link = tree.links.new(src_socket, dst_socket)
        link.is_muted = input.get("muted", False)
