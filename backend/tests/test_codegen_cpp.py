"""Export validation and unchanged Python generation using actual nodes."""

import subprocess

import pytest

from app.models.graph import Edge, Graph, NodeInstance
from app.services.codegen import generate_python
from app.services.cpp_codegen import CppExportError, generate_cpp


def blank():
    return NodeInstance(id="图像 ' source", type="blank_image")


def test_complete_source():
    code = generate_cpp(Graph(nodes=[blank()])).code
    assert "int main()" in code
    assert "void run_pipeline()" in code
    assert "cv::Mat n0_image" in code
    assert "Python" not in code


@pytest.mark.parametrize("graph", [
    Graph(),
    Graph(nodes=[blank(), blank()]),
    Graph(nodes=[NodeInstance(id="x", type="custom_python")]),
    Graph(nodes=[NodeInstance(id="x", type="gaussian_noise")]),
    Graph(nodes=[NodeInstance(id="x", type="resize")]),
    Graph(nodes=[NodeInstance(id="x", type="blank_image", params={"width": "32"})]),
    Graph(nodes=[NodeInstance(id="x", type="blank_image", params={"width": 0})]),
    Graph(nodes=[NodeInstance(id="x", type="load_image", params={"asset_batch_id": "missing"})]),
    Graph(nodes=[blank()], edges=[Edge(id="e", source="missing", target=blank().id)]),
    Graph(nodes=[NodeInstance(id="a", type="preview"), NodeInstance(id="b", type="preview")],
          edges=[Edge(id="e1", source="a", target="b"), Edge(id="e2", source="b", target="a")]),
    Graph(nodes=[NodeInstance(id="a", type="blank_image"), NodeInstance(id="b", type="preview")],
          edges=[Edge(id="e1", source="a", target="b", target_port="missing")]),
    Graph(nodes=[NodeInstance(id="a", type="blank_image"), NodeInstance(id="b", type="preview")],
          edges=[Edge(id="e1", source="a", target="b"), Edge(id="e2", source="a", target="b")]),
])
def test_invalid_graphs_fail(graph):
    with pytest.raises(CppExportError) as failure:
        generate_cpp(graph)
    assert failure.value.status_code == 422
    assert failure.value.detail["message"]


def test_python_generator_matches_public_baseline():
    source = subprocess.check_output(
        ["git", "show", "baseline-20261010:backend/app/services/codegen.py"], text=True,
    )
    namespace = {}
    exec(compile(source, "baseline-codegen.py", "exec"), namespace)
    graph = Graph(nodes=[NodeInstance(id="blank", type="blank_image"),
                        NodeInstance(id="blur", type="gaussian_blur")],
                  edges=[Edge(id="e", source="blank", target="blur")])
    assert generate_python(graph, 12) == namespace["generate_python"](graph, 12)
