from .node_dsl import NodeGraph
from .material_util import group

from bpy.types import (
    ShaderNodeTree,
    NodeSocketFloat,
    NodeSocketVector,
    NodeSocketColor,
    NodeSocketShader,
    NodeGroupInput,
    NodeGroupOutput,
    ShaderNodeGroup,
    ShaderNodeBsdfPrincipled,
    ShaderNodeTexCoord,
    ShaderNodeVectorMath,
    ShaderNodeMix,
    ShaderNodeMath,
    ShaderNodeSeparateXYZ,
    ShaderNodeCombineXYZ,
    ShaderNodeValToRGB,
    ShaderNodeBump,
)


@group("LEGO Standard")
def lego_standard(graph: NodeGraph[ShaderNodeTree]) -> None:
    graph.input(NodeSocketColor, "Color")
    graph.input(NodeSocketFloat, "Roughness")
    graph.input(NodeSocketFloat, "Specular")
    graph.input(NodeSocketVector, "Normal")
    graph.output(NodeSocketShader, "Shader")

    input = graph.node(NodeGroupInput)

    concave_walls = graph.node(
        ShaderNodeGroup,
        node_tree=concave_walls(),
        inputs={"Strength": 0.08, "Normal": input["Normal"]},
    )

    bsdf = graph.node(
        ShaderNodeBsdfPrincipled,
        inputs={
            "Base Color": input["Color"],
            "Roughness": input["Roughness"],
            "IOR": 1.45,
            "Normal": concave_walls,
            "IOR Level": input["Specular"],
        },
    )

    graph.node(NodeGroupOutput, inputs=[bsdf])


@group("Concave Walls")
def concave_walls(graph: NodeGraph[ShaderNodeTree]) -> None:
    graph.input(NodeSocketFloat, "Strength")
    graph.input(NodeSocketVector, "Normal")

    distance_to_center = graph.node(ShaderNodeGroup, node_tree=distance_to_center())

    element_power = graph.node(
        ShaderNodeGroup,
        node_tree=vector_element_power(),
        inputs=[4.0, distance_to_center],
    )

    input = graph.node(NodeGroupInput)

    convert_to_normals = graph.node(
        ShaderNodeGroup,
        node_tree=convert_to_normals(),
        inputs={
            "Vector Length": element_power,
            "Smoothing": 0.3,
            "Strength": input["Strength"],
            "Normal": input["Normal"],
        },
    )

    graph.node(NodeGroupOutput, inputs=[convert_to_normals])


@group("Distance to Center")
def distance_to_center(graph: NodeGraph[ShaderNodeTree]) -> None:
    graph.output(NodeSocketVector, "Vector")

    tex_coord = graph.node(ShaderNodeTexCoord)

    subtract_1 = graph.node(
        ShaderNodeVectorMath,
        operation="SUBTRACT",
        inputs=[tex_coord["Generated"], (0.5, 0.5, 0.5)],
    )

    normalize = graph.node(
        ShaderNodeVectorMath, operation="NORMALIZE", inputs=[tex_coord["Normal"]]
    )

    dot_product = graph.node(
        ShaderNodeVectorMath, operation="DOT_PRODUCT", inputs=[subtract_1, normalize]
    )

    multiply = graph.node(
        ShaderNodeMix,
        data_type="RGBA",
        blend_type="MULTIPLY",
        inputs={"Factor": 1.0, "A": dot_product, "B": normalize},
    )

    subtract_2 = graph.node(
        ShaderNodeVectorMath, operation="SUBTRACT", inputs=[subtract_1, multiply]
    )

    graph.node(NodeGroupOutput, inputs=[multiply])


@group("Vector Element Power")
def vector_element_power(graph: NodeGraph[ShaderNodeTree]) -> None:
    graph.input(NodeSocketFloat, "Exponent")
    graph.input(NodeSocketVector, "Vector")
    graph.output(NodeSocketVector, "Vector")

    input = graph.node(NodeGroupInput)

    separate = graph.node(ShaderNodeSeparateXYZ, inputs=[input["Vector"]])

    elements = {}
    for w in ("X", "Y", "Z"):
        absolute = graph.node(
            ShaderNodeMath, operation="ABSOLUTE", inputs=[separate[w]]
        )

        power = graph.node(
            ShaderNodeMath,
            operation="POWER",
            inputs={
                "Base": absolute,
                "Exponent": input["Exponent"],
            },
        )

        elements[w] = power

    combine = graph.node(
        ShaderNodeCombineXYZ,
        inputs={"X": elements["X"], "Y": elements["Y"], "Z": elements["Z"]},
    )

    graph.node(NodeGroupOutput, inputs=[combine])


@group("Convert to Normals")
def convert_to_normals(graph: NodeGraph[ShaderNodeTree]) -> None:
    graph.input(NodeSocketFloat, "Vector Length")
    graph.input(NodeSocketFloat, "Smoothing")
    graph.input(NodeSocketFloat, "Strength")
    graph.input(NodeSocketVector, "Normal")
    graph.output(NodeSocketVector, "Normal")

    input = graph.node(NodeGroupInput)

    power = graph.node(
        ShaderNodeMath,
        operation="POWER",
        inputs={"Base": input["Vector Length"], "Exponent": input["Smoothing"]},
    )

    ramp = graph.node(ShaderNodeValToRGB, inputs=[power])
    ramp.node.color_ramp.interpolation = "EASE"
    ramp.node.color_ramp.elements[0].color = (1.0, 1.0, 1.0, 1.0)
    ramp.node.color_ramp.elements[1].color = (0.0, 0.0, 0.0, 1.0)
    ramp.node.color_ramp.elements[1].position = 0.45

    bump = graph.node(
        ShaderNodeBump,
        inputs={
            "Strength": input["Strength"],
            "Distance": 0.02,
            "Height": ramp["Color"],
            "Normal": input["Normal"],
        },
    )

    graph.node(NodeGroupOutput, inputs=[bump])
