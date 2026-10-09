"""Validate and generate a complete native C++17 OpenCV pipeline."""

import math
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException

from app.engine.registry import registry
from app.models.graph import Graph, PortDirection
from app.nodes import register_builtin_nodes
from app.nodes.io import resolve_load_paths

from . import analysis, clustering, color, common, filters, geometry, io, morphology, structure
from . import math as image_math

MODULES = (io, color, filters, analysis, geometry, image_math, morphology, clustering, structure)
EMITTERS = {kind: module.emit for module in MODULES for kind in module.TYPES}
SUPPORTED_TYPES = frozenset(EMITTERS)


class CppExportError(HTTPException):
    """A located export validation failure, directly handled by FastAPI."""

    def __init__(self, message: str, node_id: str | None = None, node_type: str | None = None):
        super().__init__(422, {"message": message, "node_id": node_id, "node_type": node_type})


@dataclass(frozen=True)
class CppExport:
    code: str
    filename: str
    dependencies: list[str]


def fail(message, node=None):
    raise CppExportError(message, node.id if node else None, node.type if node else None)


def validated_params(node):
    impl = registry.get(node.type)
    params = impl.default_params() | node.params
    for field in impl.params:
        value = params[field.name]
        if field.type in {"integer", "int"}:
            if type(value) is not int:
                fail(f"Parameter '{field.name}' must be an integer", node)
        elif field.type == "number":
            if type(value) not in {int, float} or not math.isfinite(value):
                fail(f"Parameter '{field.name}' must be a finite number", node)
        elif not isinstance(value, str):
            fail(f"Parameter '{field.name}' must be a string", node)
        if field.options is not None and value not in field.options:
            fail(f"Parameter '{field.name}' must be one of {field.options}", node)
        if type(value) in {int, float}:
            if field.minimum is not None and value < field.minimum:
                fail(f"Parameter '{field.name}' below minimum {field.minimum}", node)
            if field.maximum is not None and value > field.maximum:
                fail(f"Parameter '{field.name}' above maximum {field.maximum}", node)
        if isinstance(value, str) and "\0" in value:
            fail(f"Parameter '{field.name}' contains a null character", node)
    return params


def validate(graph):
    register_builtin_nodes()
    if not graph.nodes:
        fail("Cannot export an empty workflow")
    nodes = {}
    parameters = {}
    for node in graph.nodes:
        if node.id in nodes:
            fail("Duplicate node id", node)
        if node.type not in EMITTERS:
            fail("This node does not support C++ export", node)
        nodes[node.id] = node
        parameters[node.id] = validated_params(node)
    incoming = {node_id: {} for node_id in nodes}
    successors = {node_id: [] for node_id in nodes}
    indegree = dict.fromkeys(nodes, 0)
    edge_ids = set()
    for edge in graph.edges:
        if edge.id in edge_ids:
            fail(f"Duplicate edge id '{edge.id}'")
        edge_ids.add(edge.id)
        if edge.source not in nodes or edge.target not in nodes:
            fail(f"Edge '{edge.id}' refers to an unknown node")
        target = nodes[edge.target]
        source_ports = {p.id: p for p in registry.get(nodes[edge.source].type).ports
                        if p.direction == PortDirection.OUTPUT}
        target_ports = {p.id: p for p in registry.get(target.type).ports
                        if p.direction == PortDirection.INPUT}
        if edge.source_port not in source_ports or edge.target_port not in target_ports:
            fail(f"Edge '{edge.id}' refers to an unknown port", target)
        if source_ports[edge.source_port].data_type != target_ports[edge.target_port].data_type:
            fail(f"Edge '{edge.id}' connects incompatible port types", target)
        if edge.target_port in incoming[edge.target]:
            fail(f"Multiple connections to input '{edge.target_port}'", target)
        incoming[edge.target][edge.target_port] = edge
        successors[edge.source].append(edge.target)
        indegree[edge.target] += 1
    for node in graph.nodes:
        for port in registry.get(node.type).ports:
            if port.direction == PortDirection.INPUT and not port.optional:
                if port.id not in incoming[node.id]:
                    fail(f"Missing required input '{port.id}'", node)
    queue = deque(sorted(n for n, count in indegree.items() if count == 0))
    order = []
    while queue:
        current = queue.popleft()
        order.append(current)
        for child in sorted(successors[current]):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if len(order) != len(nodes):
        fail("Workflow contains a cycle", nodes[next(n for n, count in indegree.items() if count)])
    return nodes, parameters, incoming, order


def generate_cpp(graph: Graph, seed: int = 0, iteration_count: int = 1) -> CppExport:
    """Export the complete graph using real native OpenCV operations."""
    if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        fail("Seed must be an integer between 0 and 4294967295")
    if type(iteration_count) is not int or not 1 <= iteration_count <= 2**31 - 1:
        fail("Iteration count must be a positive 32-bit integer")
    nodes, parameters, incoming, order = validate(graph)
    zip_enabled = any(n.type == "save_image" and parameters[n.id]["packaging"] == "zip"
                      for n in graph.nodes)
    dependencies = ["opencv"] + (["libarchive"] if zip_enabled else [])
    config = [f"const uint64_t pipeline_seed = {seed}ULL;",
              f"const size_t pipeline_iterations = {iteration_count};"]
    load_code = []
    variables = {}
    batch_size = 1
    for index, node_id in enumerate(order):
        node = nodes[node_id]
        params = parameters[node_id]
        variables[node_id] = {p.id: f"n{index}_{p.id}"
                              for p in registry.get(node.type).ports
                              if p.direction == PortDirection.OUTPUT}
        if node.type == "load_image":
            from app.services.assets import get_batch

            batch_id = str(params.get("asset_batch_id", "")).strip()
            if batch_id:
                batch = get_batch(batch_id)
                if batch is None:
                    fail("Asset batch was not found", node)
                paths = [Path(item.path) for item in batch.files]
            else:
                path_value = params.get("path", "")
                if not isinstance(path_value, str) or not Path(path_value).exists():
                    fail("Load Images requires existing files or an asset batch", node)
                paths = resolve_load_paths(params)
            if not paths or any(not path.is_file() for path in paths):
                fail("Input image files are missing", node)
            source = f"source_{index}"
            params["_cpp_source"] = source
            config += [f"const std::vector<std::string> {source}_paths = {{",
                       *[f"    {common.literal(str(path))}," for path in paths], "};"]
            load_code += [f"std::vector<cv::Mat> {source}_images;",
                          f"for (const auto& path : {source}_paths) {source}_images.push_back(read_image(path));"]
            batch_size = max(batch_size, len(paths))
        if node.type == "save_image":
            name = f"output_{index}"
            params["_cpp_output"] = name
            config += [f"const std::string {name} = {common.literal(params['output_dir'] or 'output')};"]
    flags = "opencv4 libarchive" if zip_enabled else "opencv4"
    lines = ["// Generated by Better Image Pipes. C++17.",
             f"// Linux: g++ -std=c++17 pipeline.cpp -o pipeline $(pkg-config --cflags --libs {flags})",
             "// Windows: compile with /std:c++17 /utf-8 and link the declared OpenCV modules.",
             "// Dependencies: " + ", ".join(dependencies),
             "// Random colors and k-means are reproducible within this native OpenCV environment.",
             common.RUNTIME, analysis.RUNTIME, clustering.RUNTIME]
    if zip_enabled:
        lines += [io.ZIP_RUNTIME]
    lines += ["\n// Editable pipeline configuration.", *config, "", "void run_pipeline() {",
              "    cv::setNumThreads(1);", *["    " + line for line in load_code]]
    if zip_enabled:
        lines += ["    ZipBuckets zip_buckets;"]
    lines += ["    for (size_t iteration = 0; iteration < pipeline_iterations; ++iteration) {",
              "        uint64_t iteration_seed = pipeline_seed + iteration;",
              "        (void)iteration_seed;",
              f"        for (size_t batch_index = 0; batch_index < {batch_size}; ++batch_index) {{",
              f"            size_t sample_index = iteration * {batch_size} + batch_index;",
              "            (void)sample_index;", "            std::string source_stem = \"image\";"]
    for node_id in order:
        node = nodes[node_id]
        output = variables[node_id]
        inputs = {port: variables[edge.source][edge.source_port]
                  for port, edge in incoming[node_id].items()}
        lines += [f"            cv::Mat {var};" for var in output.values()]
        lines += [f"            // node: {common.literal(node_id)} ({node.type})",
                  "            {",
                  f"                std::clog << \"processing \" << {common.literal(node_id)} << '\\n';"]
        statements = EMITTERS[node.type](node.type, parameters[node_id], inputs, output)
        lines += ["                " + statement for statement in statements]
        for port, var in output.items():
            lines += [f"                require(!{var}.empty(), \"Empty output: \" + std::string({common.literal(node_id + ':' + port)}));",
                      f"                std::cout << \"produced \" << {common.literal(node_id + ':' + port)} << \" \" << {var}.rows << \"x\" << {var}.cols << \"x\" << {var}.channels() << '\\n';"]
        lines += ["            }"]
    lines += ["        }", "    }"]
    if zip_enabled:
        lines += ["    write_zips(zip_buckets);"]
    lines += ["}", "", "int main() {", "    run_pipeline();", "    return 0;", "}", ""]
    return CppExport("\n".join(lines), "pipeline.cpp", dependencies)
