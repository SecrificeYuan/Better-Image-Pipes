"""Image arithmetic and masks."""

TYPES = {"apply_mask", "bitwise", "absdiff", "add_weighted", "arithmetic"}


def emit(kind, p, i, o):
    d = o["image"]
    if kind == "apply_mask":
        s = i["image"]
        lines = [f"cv::Mat mask = resize_to(as_gray({i['mask']}), {s}.size(), cv::INTER_NEAREST);"]
        if p["fill"] == "unchanged":
            return lines + [f"{d} = {s}.clone();"]
        lines += [f"cv::bitwise_and({s}, {s}, {d}, mask);"]
        if p["fill"] == "white":
            lines += [
                "cv::Mat inverse, background; cv::bitwise_not(mask, inverse);",
                f"cv::Mat white({s}.size(), {s}.type(), cv::Scalar::all(255));",
                "cv::bitwise_and(white, white, background, inverse);",
                f"cv::add({d}, background, {d});",
            ]
        return lines
    lines = [f"cv::Mat a = {i['a']}, b = {i['b']};", "align_pair(a, b);"]
    mask = "cv::noArray()"
    if "mask" in i:
        lines += [f"cv::Mat mask = resize_to(as_gray({i['mask']}), a.size(), cv::INTER_NEAREST);"]
        mask = "mask"
    if kind == "absdiff":
        return lines + [f"cv::absdiff(a, b, {d});"]
    if kind == "add_weighted":
        return lines + [f"cv::addWeighted(a, {p['alpha']}, b, {p['beta']}, {p['gamma']}, {d});"]
    if kind == "bitwise":
        return lines + [f"cv::bitwise_{p['op']}(a, b, {d}, {mask});"]
    if kind == "arithmetic":
        if p["op"] == "multiply":
            lines += [f"cv::multiply(a, b, {d});"]
            if "mask" in i:
                lines += [f"cv::Mat masked; cv::bitwise_and({d}, {d}, masked, mask); {d} = masked;"]
        else:
            lines += [f"cv::{p['op']}(a, b, {d}, {mask});"]
        return lines
    raise AssertionError(kind)
