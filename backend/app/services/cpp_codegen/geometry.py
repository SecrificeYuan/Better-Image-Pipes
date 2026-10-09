"""Geometric transform emitters."""

TYPES = {"resize", "rotate", "crop", "flip"}


def emit(kind, p, i, o):
    s, d = i["image"], o["image"]
    if kind == "resize":
        return [f"cv::resize({s}, {d}, cv::Size({p['width']}, {p['height']}), 0, 0, cv::INTER_LINEAR);"]
    if kind == "rotate":
        return [f"cv::Mat matrix = cv::getRotationMatrix2D(cv::Point2f({s}.cols / 2.0f, {s}.rows / 2.0f), {p['angle']}, 1.0);",
                f"cv::warpAffine({s}, {d}, matrix, {s}.size());"]
    if kind == "crop":
        return [f"int x = std::min({p['x']}, {s}.cols), y = std::min({p['y']}, {s}.rows);",
                f"int width = std::min({p['width']}, {s}.cols - x), height = std::min({p['height']}, {s}.rows - y);",
                "require(width > 0 && height > 0, \"Crop produced an empty image\");",
                f"{d} = {s}(cv::Rect(x, y, width, height)).clone();"]
    if kind == "flip":
        code = {"horizontal": 1, "vertical": 0, "both": -1}[p["mode"]]
        return [f"cv::flip({s}, {d}, {code});"]
    raise AssertionError(kind)
