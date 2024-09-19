import bpy
from .node_dsl import ShaderGraph

from bpy.types import (
    NodeSocketInt,
    NodeSocketFloat,
    NodeSocketColor,
    NodeSocketBool,
    NodeSocketVector,
    NodeGroupInput,
    NodeGroupOutput,
    ShaderNodeObjectInfo,
    ShaderNodeTree,
    ShaderNodeMath,
    ShaderNodeGroup,
    NodeTreeInterfaceSocketInt,
    ShaderNodeMapRange,
    ShaderNodeMix,
    ShaderNodeTexCoord,
    ShaderNodeSeparateXYZ,
    ShaderNodeCombineXYZ,
    ShaderNodeVectorTransform,
    ShaderNodeVectorMath,
    ShaderNodeAttribute,
)


# Copied directly from material.py. Whatever.
def is_slope_node_group(graph: ShaderGraph) -> None:
    graph.output(NodeSocketFloat, "Factor")

    # Apply grainy normals to faces that aren't vertical or horizontal.
    # Use non transformed normals to not consider object rotation.
    ldr_normals = graph.node(ShaderNodeAttribute, attribute_name="ldr_normals")
    ldr_normals.node.location = (-1600, 400)

    separate = graph.node(ShaderNodeSeparateXYZ, [ldr_normals["Vector"]])
    separate.node.location = (-1400, 400)

    # Use normal.y to check if the face is horizontal (-1.0 or 1.0) or vertical (0.0).
    # Any values in between are considered "slopes" and use grainy normals.
    absolute = graph.math_node("ABSOLUTE", [separate["Y"]])
    absolute.node.location = (-1200, 400)
    compare = graph.math_node("COMPARE", [absolute, 0.5, 0.45])
    compare.node.location = (-1000, 400)

    is_stud = graph.node(ShaderNodeAttribute, attribute_name="ldr_is_stud")
    is_stud.node.location = (-1000, 200)

    # Don't apply the grainy slopes to any faces marked as studs.
    # We use an attribute here to avoid per face material assignment.
    subtract_studs = graph.math_node("SUBTRACT", [compare, is_stud["Fac"]])
    subtract_studs.node.location = (-800, 400)

    output = graph.node(NodeGroupOutput, [subtract_studs])
    output.node.location = (-600, 400)


# Copied directly from material.py. Whatever.
def object_scale_node_group(graph: ShaderGraph) -> None:
    graph.output(NodeSocketFloat, "Value")

    transform = graph.node(
        ShaderNodeVectorTransform,
        vector_type="VECTOR",
        convert_from="OBJECT",
        convert_to="WORLD",
        inputs=[(1.0, 0.0, 0.0)],
    )

    length = graph.node(ShaderNodeVectorMath, operation="LENGTH", inputs=[transform])
    length.node.location = (200, 0)

    output = graph.node(NodeGroupOutput, [length])
    output.node.location = (400, 0)


def uv_degradation_node_group(graph: ShaderGraph) -> None:
    graph.input(NodeSocketColor, "FromColor")
    graph.input(NodeSocketColor, "ToColor")
    graph.input(NodeSocketFloat, "MinColorRatio")
    graph.input(NodeSocketFloat, "MaxColorRatio")
    graph.input(NodeSocketFloat, "MinRoughness")
    graph.input(NodeSocketFloat, "MaxRoughness")
    graph.input(NodeSocketFloat, "Strength")
    graph.input(NodeSocketBool, "enable")
    graph.input(NodeSocketInt, "Levels")

    graph.output(NodeSocketColor, "OutColor")
    graph.output(NodeSocketFloat, "OutRoughness")

    levels_socket: NodeTreeInterfaceSocketInt = graph.tree.interface.items_tree[
        "Levels"
    ]  # type:ignore
    levels_socket.min_value = 1
    levels_socket.default_value = 4
    levels_socket.max_value = 10

    input = graph.node(NodeGroupInput)
    object_info = graph.node(ShaderNodeObjectInfo)

    step_1 = graph.math_node("MULTIPLY", [object_info["Random"], input["Levels"]])

    step_2 = graph.math_node("FLOOR", [step_1])

    step_3 = graph.math_node("SUBTRACT", [input["Levels"], 1.0])

    t = graph.math_node(
        "DIVIDE",
        use_clamp=True,
        inputs=[step_2, step_3],
        label="t",
    )

    input2 = graph.node(NodeGroupInput, label="Group Input (Strength)")

    color_ratio = graph.node(
        ShaderNodeMapRange,
        {
            "Value": t,
            "To Min": input2["MinColorRatio"],
            "To Max": input2["MaxColorRatio"],
        },
        label="ColorRatio",
    )

    color_t = graph.math_node(
        "MULTIPLY", [color_ratio, input2["Strength"]], label="color_t"
    )

    t_strength = graph.math_node(
        "MULTIPLY", [t, input2["Strength"]], label="t * Strength"
    )

    input3 = graph.node(NodeGroupInput, label="Group Input (Ranges)")

    out_color = graph.node(
        ShaderNodeMix,
        data_type="RGBA",
        label="OutColor",
        inputs={0: color_t, "A": input3["FromColor"], "B": input3["ToColor"]},
    )

    out_roughness = graph.node(
        ShaderNodeMapRange,
        label="OutRoughness",
        clamp=False,
        inputs={
            "Value": t_strength,
            "To Min": input3["MinRoughness"],
            "To Max": input3["MaxRoughness"],
        },
    )

    input4 = graph.node(NodeGroupInput, label="Group Input (Toggles)")

    toggle_out_color = graph.node(
        ShaderNodeMix,
        label="Color Toggle",
        data_type="RGBA",
        inputs={0: input4["enable"], "A": input4["FromColor"], "B": out_color},
    )

    toggle_out_roughness = graph.node(
        ShaderNodeMix,
        label="Roughness Toggle",
        data_type="FLOAT",
        inputs={0: input4["enable"], "A": input4["MinRoughness"], "B": out_roughness},
    )

    graph.node(
        NodeGroupOutput,
        {"OutColor": toggle_out_color, "OutRoughness": toggle_out_roughness},
    )


def project_to_axis_plane_node_group(graph: ShaderGraph) -> None:
    graph.input(NodeSocketVector, "In")
    graph.output(NodeSocketVector, "Out")

    input = graph.node(NodeGroupInput)

    tex_coord = graph.node(ShaderNodeTexCoord)

    split_normal = graph.node(
        ShaderNodeSeparateXYZ, [tex_coord["Normal"]], label="Split Normal"
    )

    abs_x = graph.math_node("ABSOLUTE", [split_normal["X"]], label="Abs(X)")
    abs_y = graph.math_node("ABSOLUTE", [split_normal["Y"]], label="Abs(Y)")

    facing_x = graph.math_node("GREATER_THAN", [abs_x, 0.5], label="Facing X")
    facing_y = graph.math_node("GREATER_THAN", [abs_y, 0.5], label="Facing Y")

    transform = graph.node(
        ShaderNodeVectorTransform,
        vector_type="VECTOR",
        convert_from="WORLD",
        convert_to="OBJECT",
        inputs=[input],
    )

    object_scale = graph.group_node(object_scale_node_group)

    apply_scale = graph.node(
        ShaderNodeVectorMath, operation="MULTIPLY", inputs=[transform, object_scale]
    )

    split_pos = graph.node(ShaderNodeSeparateXYZ, [apply_scale], label="Split Position")

    # technically XYZ is redundant but the uniformity it easier to maintain and think about
    xyz = graph.node(
        ShaderNodeCombineXYZ, [split_pos["X"], split_pos["Y"], split_pos["Z"]]
    )
    xyz.node.label = "XYZ"

    xzy = graph.node(
        ShaderNodeCombineXYZ, [split_pos["X"], split_pos["Z"], split_pos["Y"]]
    )
    xzy.node.label = "XZY"

    yzx = graph.node(
        ShaderNodeCombineXYZ, [split_pos["Y"], split_pos["Z"], split_pos["X"]]
    )
    yzx.node.label = "YZX"

    elif_facing_x = graph.node(
        ShaderNodeMix,
        label="elseif facing X",
        data_type="VECTOR",
        inputs={"Factor": facing_x, "B": yzx, "A": xyz},
    )

    if_facing_y = graph.node(
        ShaderNodeMix,
        label="if facing Y",
        data_type="VECTOR",
        inputs={"Factor": facing_y, "B": xzy, "A": elif_facing_x},
    )

    graph.node(NodeGroupOutput, [if_facing_y])
