"""Morphology emitters."""

from .common import odd

TYPES = {"erode", "dilate", "morphology_ex"}


def emit(kind, p, i, o):
    s, d = i["image"], o["image"]
    k = odd(p["ksize"])
    shape = p["shape"].upper()
    lines = [f"cv::Mat kernel = cv::getStructuringElement(cv::MORPH_{shape}, cv::Size({k},{k}));"]
    if kind == "morphology_ex":
        lines += [f"cv::morphologyEx({s}, {d}, cv::MORPH_{p['op'].upper()}, kernel);"]
    else:
        lines += [f"cv::{kind}({s}, {d}, kernel, cv::Point(-1,-1), {p['iterations']});"]
    return lines
