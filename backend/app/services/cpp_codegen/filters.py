"""Filter and threshold emitters."""

from .common import odd

TYPES = {"gaussian_blur", "median_blur", "box_blur", "bilateral_filter", "sharpen",
         "canny", "sobel", "laplacian", "threshold"}


def emit(kind, p, i, o):
    s, d = i["image"], o["image"]
    k = odd(p["ksize"]) if "ksize" in p else 0
    if kind == "gaussian_blur":
        return [f"cv::GaussianBlur({s}, {d}, cv::Size({k}, {k}), {p['sigma']});"]
    if kind == "median_blur":
        return [f"cv::medianBlur({s}, {d}, {k});"]
    if kind == "box_blur":
        return [f"cv::boxFilter({s}, {d}, -1, cv::Size({p['ksize']}, {p['ksize']}), cv::Point(-1,-1), {p['normalize']});"]
    if kind == "bilateral_filter":
        return [f"cv::bilateralFilter({s}, {d}, {p['d']}, {p['sigma_color']}, {p['sigma_space']});"]
    if kind == "sharpen":
        a = p["amount"]
        if p["kernel"] == "unsharp":
            return [f"cv::Mat blur; cv::GaussianBlur({s}, blur, cv::Size(0,0), 3);",
                    f"cv::addWeighted({s}, {1+a}, blur, {-a}, 0, {d});"]
        return [f"cv::Mat kernel = (cv::Mat_<float>(3,3) << 0,-1,0,-1,{4*a+1},-1,0,-1,0);",
                f"cv::filter2D({s}, {d}, -1, kernel);"]
    if kind == "canny":
        return [f"cv::Canny(as_gray({s}), {d}, {p['threshold1']}, {p['threshold2']});"]
    if kind == "threshold":
        method = p["method"]
        flags = {"binary": "BINARY", "binary_inv": "BINARY_INV", "trunc": "TRUNC",
                 "tozero": "TOZERO", "tozero_inv": "TOZERO_INV"}
        flag = "cv::THRESH_" + flags[method] if method in flags else (
            "cv::THRESH_BINARY_INV" if method.endswith("_inv") else "cv::THRESH_BINARY"
        ) + " | cv::THRESH_" + ("OTSU" if method.startswith("otsu") else "TRIANGLE")
        return [f"cv::threshold(as_gray({s}), {d}, {p['thresh']}, {p['maxval']}, {flag});"]
    if kind in {"sobel", "laplacian"}:
        if kind == "sobel":
            dx, dy = int(p["dx"]), int(p["dy"])
            if dx == dy == 0:
                dx = 1
            call = f"cv::Sobel(as_gray({s}), gradient, CV_64F, {dx}, {dy}, {k}, {p['scale']});"
        else:
            call = f"cv::Laplacian(as_gray({s}), gradient, CV_64F, {k}, {p['scale']});"
        return ["cv::Mat gradient;", call, f"cv::convertScaleAbs(gradient, {d});"]
    raise AssertionError(kind)
