"""Compile and run actual generated programs against real OpenCV results."""

import json
import os
import shlex
import subprocess
import zipfile
from pathlib import Path

import cv2
import numpy as np

from app.models.graph import Edge, Graph, NodeInstance
from app.services.cpp_codegen import SUPPORTED_TYPES, generate_cpp
from tests.helpers.cpp_codegen_cases import cases, graph_for_cases, real_image


def compile_program(code: str, directory: Path, zip_enabled=False):
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / "pipeline.cpp"
    source.write_text(code, encoding="utf-8")
    flags = subprocess.check_output(
        ["pkg-config", "--cflags", "--libs", "opencv4", *(["libarchive"] if zip_enabled else [])],
        text=True,
    )
    binary = directory / "pipeline"
    subprocess.run([os.environ.get("CXX", "g++"), "-std=c++17", "-O0", str(source),
                    "-o", str(binary), *shlex.split(flags)], check=True, capture_output=True)
    return binary


def run(binary):
    return subprocess.run([str(binary)], check=True, capture_output=True, text=True, timeout=180)


def test_all_native_nodes_and_parameters(tmp_path):
    assert cv2.__version__ == "4.13.0", "Reference tests require OpenCV 4.13.0"
    assert subprocess.check_output(["pkg-config", "--modversion", "opencv4"], text=True).strip() == "4.13.0"
    image_path = tmp_path / "实际 图像.png"
    real_image(image_path)
    coverage = set()
    records = []
    all_cases = cases()
    for offset in range(0, len(all_cases), 35):
        chunk = all_cases[offset:offset+35]
        directory = tmp_path / f"group-{offset}"
        output = directory / "images"
        graph, expected = graph_for_cases(chunk, image_path, output)
        exported = generate_cpp(graph, seed=23)
        binary = compile_program(exported.code, directory, "libarchive" in exported.dependencies)
        run(binary)
        for case in chunk:
            coverage.add(case.kind)
            for port, reference in expected[case.name].items():
                path = output / f"{case.name}-{port}.png"
                actual = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
                assert actual is not None, path
                assert actual.shape == reference.shape, case.name
                error = int(np.abs(actual.astype(np.int32)-reference.astype(np.int32)).max())
                if case.kind == "connected_components" and case.params["mode"] == "labels":
                    np.testing.assert_array_equal(np.any(actual != 0, axis=2), np.any(reference != 0, axis=2))
                elif case.kind == "kmeans_colors":
                    if case.params["output"] == "quantized":
                        assert len(np.unique(actual.reshape(-1, 3), axis=0)) <= case.params["k"]
                else:
                    tolerance = 1 if case.kind in {"normalize", "distance_transform"} else 0
                    assert error <= tolerance, (case.name, port, error)
                records.append({"case": case.name, "port": port, "max_pixel_difference": error})
        # A second real execution verifies deterministic native output, including seeded palettes.
        before = {p.name: p.read_bytes() for p in output.glob("*.png")}
        run(binary)
        for name, content in before.items():
            repeated = output / (Path(name).stem + "_2.png")
            assert repeated.read_bytes() == content, name
    assert coverage == SUPPORTED_TYPES
    report = {"opencv": cv2.__version__, "nodes": len(coverage), "cases": len(all_cases), "results": records}
    (tmp_path / "native-results.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({"native_nodes": len(coverage), "parameter_cases": len(all_cases)}))


def test_batch_branches_and_zip(tmp_path):
    files = []
    for index in range(3):
        path = tmp_path / f"批次 {index}.png"
        image = real_image(path)
        if index:
            image = cv2.flip(image, index-1)
            assert cv2.imwrite(str(path), image)
        files.append(path)
    from app.services.assets import register_paths

    batch = register_paths([str(path) for path in files], kind="external")
    output = tmp_path / "输出"
    graph = Graph(nodes=[
        NodeInstance(id="多图", type="load_image", params={"asset_batch_id": batch.id}),
        NodeInstance(id="single", type="load_image", params={"path": str(files[0])}),
        NodeInstance(id="split", type="split_channels"),
        NodeInstance(id="merge", type="merge_channels"),
        NodeInstance(id="difference", type="absdiff"),
        NodeInstance(id="save", type="save_image", params={"output_dir": str(output),
                     "filename": "{filename}_{index}.png", "packaging": "zip"}),
    ], edges=[Edge(id="a", source="多图", target="split"),
              *[Edge(id=c, source="split", source_port=c, target="merge", target_port=c) for c in "bgr"],
              Edge(id="b", source="merge", target="difference", target_port="a"),
              Edge(id="s", source="single", target="difference", target_port="b"),
              Edge(id="o", source="difference", target="save")])
    exported = generate_cpp(graph, seed=23, iteration_count=2)
    assert exported.dependencies == ["opencv", "libarchive"]
    run(compile_program(exported.code, tmp_path / "build", True))
    archives = list(output.glob("*.zip"))
    assert len(archives) == 1
    with zipfile.ZipFile(archives[0]) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == 6
        for index, name in enumerate(archive.namelist()):
            sample = int(Path(name).stem.rsplit("_", 1)[1])
            actual = cv2.imdecode(np.frombuffer(archive.read(name), np.uint8), cv2.IMREAD_UNCHANGED)
            reference = cv2.absdiff(cv2.imread(str(files[sample % 3])), cv2.imread(str(files[0])))
            np.testing.assert_array_equal(actual, reference)


def test_runtime_failures(tmp_path):
    image = tmp_path / "broken.png"
    image.write_bytes(b"This file is deliberately invalid image input for a failure test.")
    graph = Graph(nodes=[NodeInstance(id="source", type="load_image", params={"path": str(image)})])
    binary = compile_program(generate_cpp(graph).code, tmp_path / "decode")
    result = subprocess.run([str(binary)], capture_output=True, timeout=20)
    assert result.returncode != 0
    assert b"Cannot decode image" in result.stderr
    blocker = tmp_path / "blocked"
    blocker.write_text("Existing file blocks creation of an output directory.")
    graph = Graph(nodes=[NodeInstance(id="blank", type="blank_image"),
                        NodeInstance(id="save", type="save_image", params={"output_dir": str(blocker)})],
                  edges=[Edge(id="e", source="blank", target="save")])
    result = subprocess.run([str(compile_program(generate_cpp(graph).code, tmp_path / "write"))],
                            capture_output=True, timeout=20)
    assert result.returncode != 0


def test_opencv_454_compatibility(tmp_path):
    graph = Graph(nodes=[NodeInstance(id="blank", type="blank_image")])
    binary = compile_program(generate_cpp(graph).code, tmp_path)
    run(binary)
