from .node_dsl import ShaderGraph

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
    ShaderNodeSeparateColor,
    ShaderNodeCombineColor,
    ShaderNodeValToRGB,
    ShaderNodeBump,
)


def lego_standard(graph: ShaderGraph) -> None:
    graph.input(NodeSocketColor, "Color")
    graph.input(NodeSocketFloat, "Roughness", default=0.1, min_max=(0.0, 1.0))
    graph.input(NodeSocketFloat, "Specular", default=0.5, min_max=(0.0, float("inf")))
    graph.input(NodeSocketVector, "Normal")
    graph.output(NodeSocketShader, "Shader")

    input = graph.node(NodeGroupInput)

    normals = graph.group_node(concave_walls, {"Normal": input["Normal"]})

    bsdf = graph.node(
        ShaderNodeBsdfPrincipled,
        {
            "Base Color": input["Color"],
            "Roughness": input["Roughness"],
            "IOR": 1.45,
            "Normal": normals,
            "Specular IOR Level": input["Specular"],
        },
    )

    graph.node(NodeGroupOutput, [bsdf])


def concave_walls(graph: ShaderGraph) -> None:
    graph.input(NodeSocketFloat, "Strength", default=0.08)
    graph.input(NodeSocketVector, "Normal")
    graph.output(NodeSocketVector, "Normal")

    d2c = graph.group_node(distance_to_center)

    element_power = graph.group_node(vector_element_power, [4.0, d2c])

    input = graph.node(NodeGroupInput)

    normals = graph.group_node(
        convert_to_normals,
        {
            "Vector Length": element_power,
            "Smoothing": 0.3,
            "Strength": input["Strength"],
            "Normal": input["Normal"],
        },
    )

    graph.node(NodeGroupOutput, [normals])


def distance_to_center(graph: ShaderGraph) -> None:
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


def vector_element_power(graph: ShaderGraph) -> None:
    graph.input(NodeSocketFloat, "Exponent")
    graph.input(NodeSocketVector, "Vector")
    graph.output(NodeSocketVector, "Vector")

    input = graph.node(NodeGroupInput)

    separate = graph.node(ShaderNodeSeparateXYZ, [input["Vector"]])

    elements = {}
    for w in ("X", "Y", "Z"):
        absolute = graph.math_node("ABSOLUTE", [separate[w]])

        power = graph.math_node("POWER", [absolute, input["Exponent"]])

        elements[w] = power

    combine = graph.node(
        ShaderNodeCombineXYZ,
        {"X": elements["X"], "Y": elements["Y"], "Z": elements["Z"]},
    )

    graph.node(NodeGroupOutput, [combine])


def convert_to_normals(graph: ShaderGraph) -> None:
    graph.input(NodeSocketFloat, "Vector Length")
    graph.input(NodeSocketFloat, "Smoothing")
    graph.input(NodeSocketFloat, "Strength")
    graph.input(NodeSocketVector, "Normal")
    graph.output(NodeSocketVector, "Normal")

    input = graph.node(NodeGroupInput)

    power = graph.math_node("POWER", [input["Vector Length"], input["Smoothing"]])

    ramp = graph.node(ShaderNodeValToRGB, [power])
    ramp.node.color_ramp.interpolation = "EASE"
    ramp.node.color_ramp.elements[0].color = (1.0, 1.0, 1.0, 1.0)
    ramp.node.color_ramp.elements[1].color = (0.0, 0.0, 0.0, 1.0)
    ramp.node.color_ramp.elements[1].position = 0.45

    bump = graph.node(
        ShaderNodeBump,
        {
            "Strength": input["Strength"],
            "Distance": 0.02,
            "Height": ramp["Color"],
            "Normal": input["Normal"],
        },
    )

    graph.node(NodeGroupOutput, [bump])


def lego_transparent(graph: ShaderGraph) -> None:
    graph.input(NodeSocketColor, "Color", default=(1.0, 1.0, 1.0, 1.0))
    graph.input(NodeSocketFloat, "Subsurface")
    graph.input(NodeSocketFloat, "Specular", default=0.5)
    graph.input(NodeSocketFloat, "Roughness")
    graph.input(NodeSocketFloat, "IOR", default=1.5)
    graph.input(NodeSocketFloat, "Transmission", default=1.0)
    graph.input(NodeSocketFloat, "Transmission Roughness")
    graph.input(NodeSocketVector, "Normal")
    graph.output(NodeSocketShader, "Shader")

    input = graph.node(NodeGroupInput)

    # force dark colors to be brighter so they're visibly transparent
    separate_color = graph.node(
        ShaderNodeSeparateColor, mode="HSV", inputs=[input["Color"]]
    )
    clamped_value = graph.math_node(
        "MAXIMUM", use_clamp=True, inputs=[separate_color[2], 0.4]
    )
    combine_color = graph.node(
        ShaderNodeCombineColor,
        mode="HSV",
        inputs=[separate_color[0], separate_color[1], clamped_value],
    )

    mix = graph.node(
        ShaderNodeMix,
        data_type="RGBA",
        clamp_result=False,
        clamp_factor=True,
        inputs={
            "Factor": input["Subsurface"],
            "A": combine_color,
            "B": (1.0, 1.0, 1.0, 1.0),
        },
    )

    normals = graph.group_node(concave_walls, {"Normal": input["Normal"]})

    bsdf = graph.node(
        ShaderNodeBsdfPrincipled,
        subsurface_method="BURLEY",
        inputs={
            "Base Color": mix,
            "Roughness": input["Roughness"],
            "IOR": input["IOR"],
            "Normal": normals,
            "Subsurface Weight": 1.0,
            "Subsurface Radius": (1.0, 0.2, 0.1),
            "Subsurface Scale": input["Subsurface"],
            "Specular IOR Level": input["Specular"],
            "Transmission Weight": input["Transmission"],
        },
    )

    graph.node(NodeGroupOutput, [bsdf])
