"""Color node emitters."""

TYPES = {
    "to_gray",
    "to_hsv",
    "to_rgb",
    "to_bgr",
    "to_lab",
    "to_yuv",
    "to_ycrcb",
    "invert",
    "clahe",
    "brightness_contrast",
    "split_channels",
    "merge_channels",
    "in_range",
}


def emit(kind, p, i, o):
    d = o.get("image")
    if kind == "merge_channels":
        return [f"cv::merge(std::vector<cv::Mat>{{{i['b']}, {i['g']}, {i['r']}}}, {d});"]
    s = i["image"]
    if kind == "to_gray":
        return [f"{d} = as_gray({s});"]
    conversions = {
        "to_hsv": "BGR2HSV",
        "to_rgb": "BGR2RGB",
        "to_bgr": "RGB2BGR",
        "to_lab": "BGR2Lab",
        "to_yuv": "BGR2YUV",
        "to_ycrcb": "BGR2YCrCb",
    }
    if kind in conversions:
        gray = "GRAY2BGR"
        if kind == "to_bgr":
            return [
                f"cv::cvtColor({s}, {d}, {s}.channels() == 1 ? cv::COLOR_{gray} : "
                f"cv::COLOR_RGB2BGR);"
            ]
        return [
            f"cv::Mat image = {s};",
            f"if (image.channels() == 1) cv::cvtColor(image, image, cv::COLOR_{gray});",
            f"cv::cvtColor(image, {d}, cv::COLOR_{conversions[kind]});",
        ]
    if kind == "invert":
        return [f"cv::bitwise_not({s}, {d});"]
    if kind == "brightness_contrast":
        return [f"cv::convertScaleAbs({s}, {d}, {p['alpha']}, {p['beta']});"]
    if kind == "split_channels":
        return [
            f"if ({s}.channels() == 1) {{",
            *[f"    {o[k]} = {s};" for k in ("b", "g", "r")],
            "} else {",
            f"    std::vector<cv::Mat> channels; cv::split({s}, channels);",
            *[f"    {o[k]} = channels.at({n});" for n, k in enumerate(("b", "g", "r"))],
            "}",
        ]
    if kind == "clahe":
        return [
            f"auto clahe = cv::createCLAHE({p['clip_limit']}, "
            f"cv::Size({p['tile_grid']}, {p['tile_grid']}));",
            f"if ({s}.channels() == 1) clahe->apply({s}, {d});",
            "else {",
            f"    cv::Mat lab; cv::cvtColor({s}, lab, cv::COLOR_BGR2Lab);",
            "    std::vector<cv::Mat> channels; cv::split(lab, channels);",
            "    clahe->apply(channels[0], channels[0]); cv::merge(channels, lab);",
            f"    cv::cvtColor(lab, {d}, cv::COLOR_Lab2BGR);",
            "}",
        ]
    if kind == "in_range":
        lines = [f"cv::Mat bgr = as_bgr({s}), converted, mask;"]
        if p["space"] != "bgr":
            flag = {"hsv": "BGR2HSV", "lab": "BGR2Lab"}[p["space"]]
            lines += [f"cv::cvtColor(bgr, converted, cv::COLOR_{flag});"]
        else:
            lines += ["converted = bgr;"]
        lo = ", ".join(str(p[f"c{n}_min"]) for n in range(3))
        hi = ", ".join(str(p[f"c{n}_max"]) for n in range(3))
        lines += [f"cv::inRange(converted, cv::Scalar({lo}), cv::Scalar({hi}), mask);"]
        lines += [
            f"cv::bitwise_and(bgr, bgr, {d}, mask);"
            if p["output"] == "masked_bgr"
            else f"{d} = mask;"
        ]
        return lines
    raise AssertionError(kind)
