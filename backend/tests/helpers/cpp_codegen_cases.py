"""Real image inputs and executable export coverage cases."""

from dataclasses import dataclass
from pathlib import Path

import cv2

from app.engine.registry import registry
from app.models.graph import Edge, Graph, NodeInstance
from app.services.cpp_codegen import SUPPORTED_TYPES


@dataclass
class Case:
    name: str
    kind: str
    params: dict


def cases():
    result = []
    for kind in sorted(SUPPORTED_TYPES):
        impl = registry.get(kind)
        result.append(Case(kind, kind, impl.default_params()))
        for field in impl.params:
            if field.options:
                for option in field.options:
                    if option != field.default:
                        result.append(Case(f"{kind}-{field.name}-{option}", kind,
                                           impl.default_params() | {field.name: option}))
        for field in impl.params:
            if field.type in {"int", "integer", "number"}:
                for label, value in (("min", field.minimum), ("max", field.maximum)):
                    if value is None or value == field.default:
                        continue
                    # Coordinates at the image edge produce empty crops; these are failure cases.
                    if kind == "crop" and field.name in {"x", "y"} and value >= 128:
                        continue
                    # Sobel derivative order must fit the kernel aperture.
                    if kind == "sobel" and field.name == "ksize" and value == 1:
                        pass
                    if field.type in {"int", "integer"}:
                        value = int(value)
                    result.append(Case(f"{kind}-{field.name}-{label}", kind,
                                       impl.default_params() | {field.name: value}))
    return result


def real_image(path: Path):
    sample = Path(__file__).resolve().parents[2] / "examples/lena.png"
    image = cv2.imread(str(sample), cv2.IMREAD_COLOR)
    assert image is not None, sample
    image = cv2.resize(image, (128, 128))
    assert cv2.imwrite(str(path), image)
    return image


def graph_for_cases(items, image_path: Path, output: Path):
    nodes = [NodeInstance(id="source", type="load_image", params={"path": str(image_path)})]
    edges = []
    expected = {}
    image = cv2.imread(str(image_path))
    assert image is not None
    for case in items:
        params = case.params.copy()
        kind = case.kind
        impl = registry.get(kind)
        if kind == "load_image":
            params["path"] = str(image_path)
        if kind == "save_image":
            params.update(output_dir=str(output / (case.name + "-saved")))
        nodes.append(NodeInstance(id=case.name, type=kind, params=params))
        inputs = {}
        for port in impl.ports:
            if port.direction.value == "input" and not port.optional:
                source = "source"
                inputs[port.id] = image.copy()
                if port.id == "mask":
                    mask_id = case.name + "-mask"
                    nodes.append(NodeInstance(id=mask_id, type="to_gray"))
                    edges.append(Edge(id=mask_id, source="source", target=mask_id))
                    source = mask_id
                    inputs[port.id] = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                edges.append(Edge(id=case.name + "-" + port.id, source=source,
                                  target=case.name, target_port=port.id))
        if kind == "load_image":
            expected[case.name] = {"image": image}
        elif kind == "save_image":
            expected[case.name] = {"image": image}
        else:
            cv2.setRNGSeed(23)
            expected[case.name] = impl.execute(inputs, params, seed=23)
        for port in impl.ports:
            if port.direction.value != "output":
                continue
            save_id = case.name + "-observe-" + port.id
            nodes.append(NodeInstance(id=save_id, type="save_image", params={
                "output_dir": str(output), "filename": case.name + "-" + port.id + ".png",
            }))
            edges.append(Edge(id=save_id, source=case.name, source_port=port.id, target=save_id))
    return Graph(nodes=nodes, edges=edges), expected
