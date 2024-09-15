from typing import Callable, TypeVar, overload, TypeAlias

import bpy
from bpy.types import NodeTree, ShaderNodeTree

from .node_dsl import NodeGraph

T = TypeVar("T", bound=NodeTree)


TreeInitializer: TypeAlias = Callable[[NodeGraph[T]], None]
TreeConstructor: TypeAlias = Callable[[], T]


@overload
def group(
    name: str,
) -> Callable[[TreeInitializer[ShaderNodeTree]], TreeConstructor[ShaderNodeTree]]: ...


@overload
def group(
    name: str,
    ty: type[T],
) -> Callable[[TreeInitializer[T]], TreeConstructor[T]]: ...


def group(
    name: str,
    ty: type | None = None,
) -> Callable[[TreeInitializer], TreeConstructor]:
    if ty is None:
        return group(name, ShaderNodeTree)

    def build_node(f: Callable[[NodeGraph], None]) -> NodeTree:
        if tree := bpy.data.node_groups.get(name):
            assert isinstance(tree, ty)
            return tree

        tree = bpy.data.node_groups.new(name, "ShaderNodeTree")  # type: ignore[arg-type]
        assert isinstance(tree, ty)
        return tree

    return lambda f: lambda: build_node(f)
