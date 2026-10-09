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


@pytest.mark.parametrize(
    "graph",
    [
        Graph(),
        Graph(nodes=[blank(), blank()]),
        Graph(nodes=[NodeInstance(id="x", type="custom_python")]),
        Graph(nodes=[NodeInstance(id="x", type="gaussian_noise")]),
        Graph(nodes=[NodeInstance(id="x", type="resize")]),
        Graph(nodes=[NodeInstance(id="x", type="blank_image", params={"width": "32"})]),
        Graph(nodes=[NodeInstance(id="x", type="blank_image", params={"width": 0})]),
        Graph(
            nodes=[NodeInstance(id="x", type="load_image", params={"asset_batch_id": "missing"})]
        ),
        Graph(nodes=[blank()], edges=[Edge(id="e", source="missing", target=blank().id)]),
        Graph(
            nodes=[NodeInstance(id="a", type="preview"), NodeInstance(id="b", type="preview")],
            edges=[Edge(id="e1", source="a", target="b"), Edge(id="e2", source="b", target="a")],
        ),
        Graph(
            nodes=[NodeInstance(id="a", type="blank_image"), NodeInstance(id="b", type="preview")],
            edges=[Edge(id="e1", source="a", target="b", target_port="missing")],
        ),
        Graph(
            nodes=[NodeInstance(id="a", type="blank_image"), NodeInstance(id="b", type="preview")],
            edges=[Edge(id="e1", source="a", target="b"), Edge(id="e2", source="a", target="b")],
        ),
    ],
)
def test_invalid_graphs_fail(graph):
    with pytest.raises(CppExportError) as failure:
        generate_cpp(graph)
    assert failure.value.status_code == 422
    assert failure.value.detail["message"]


def test_python_generator_matches_public_baseline():
    source = subprocess.check_output(
        ["git", "show", "baseline-20261010:backend/app/services/codegen.py"],
        text=True,
    )
    namespace = {}
    exec(compile(source, "baseline-codegen.py", "exec"), namespace)
    graph = Graph(
        nodes=[
            NodeInstance(id="blank", type="blank_image"),
            NodeInstance(id="blur", type="gaussian_blur"),
        ],
        edges=[Edge(id="e", source="blank", target="blur")],
    )
    assert generate_python(graph, 12) == namespace["generate_python"](graph, 12)


@pytest.mark.parametrize(
    "values",
    [
        {"seed": True},
        {"seed": 1.5},
        {"seed": -1},
        {"seed": 4294967296},
        {"iteration_count": 0},
        {"iteration_count": "2"},
    ],
)
def test_real_api_rejects_invalid_request_fields(values):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        response = client.post(
            "/api/codegen/cpp",
            json={
                "graph": Graph(nodes=[blank()]).model_dump(),
                **values,
            },
        )
    assert response.status_code == 422


def test_resource_and_parameter_validation(tmp_path):
    unsupported = tmp_path / "image.txt"
    unsupported.write_text("Unsupported input extension")
    for path in (tmp_path / "missing.png", tmp_path, unsupported):
        with pytest.raises(CppExportError) as failure:
            generate_cpp(
                Graph(
                    nodes=[NodeInstance(id="input", type="load_image", params={"path": str(path)})]
                )
            )
        assert failure.value.detail["node_id"] == "input"
    for params in ({"min_area": 5001.0}, {"min_convexity": 0.0}):
        with pytest.raises(CppExportError) as failure:
            generate_cpp(
                Graph(
                    nodes=[
                        NodeInstance(id="source", type="blank_image"),
                        NodeInstance(id="blob", type="blob_detect", params=params),
                    ],
                    edges=[Edge(id="e", source="source", target="blob")],
                )
            )
        assert failure.value.detail["node_id"] == "blob"


def test_duplicate_edge_id_rejected():
    graph = Graph(
        nodes=[
            NodeInstance(id="source", type="blank_image"),
            NodeInstance(id="one", type="preview"),
            NodeInstance(id="two", type="preview"),
        ],
        edges=[
            Edge(id="same", source="source", target="one"),
            Edge(id="same", source="source", target="two"),
        ],
    )
    with pytest.raises(CppExportError, match="Duplicate edge id"):
        generate_cpp(graph)
