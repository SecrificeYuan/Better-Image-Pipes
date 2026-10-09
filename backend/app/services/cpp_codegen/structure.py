"""Contour, shape, and connected-component emitters."""

TYPES = {
    "find_contours",
    "convex_hull",
    "moments",
    "connected_components",
    "blob_detect",
    "bounding_rect",
    "approx_poly",
}


def emit(kind, p, i, o):
    s, d = i["image"], o["image"]
    canvas = (
        f"cv::Mat::zeros({s}.size(), CV_MAKETYPE({s}.depth(), 3))"
        if p["overlay"] == "blank"
        else f"as_bgr({s})"
    )
    lines = [f"{d} = {canvas};"]
    if kind == "blob_detect":
        return lines + [
            "cv::SimpleBlobDetector::Params parameters;",
            "parameters.filterByArea = parameters.filterByCircularity = true;",
            "parameters.filterByConvexity = parameters.filterByInertia = true;",
            "parameters.filterByColor = false;",
            *[
                f"parameters.{c} = {p[k]};"
                for c, k in (
                    ("minArea", "min_area"),
                    ("maxArea", "max_area"),
                    ("minCircularity", "min_circularity"),
                    ("minConvexity", "min_convexity"),
                    ("minInertiaRatio", "min_inertia"),
                )
            ],
            "std::vector<cv::KeyPoint> points;",
            f"cv::SimpleBlobDetector::create(parameters)->detect(as_gray({s}), points);",
            f"cv::drawKeypoints({d}, points, {d}, cv::Scalar(0,140,255), "
            f"cv::DrawMatchesFlags::DRAW_RICH_KEYPOINTS);",
        ]
    lines += [f"cv::Mat binary = binary_image({s});"]
    if kind == "connected_components":
        lines += [
            "cv::Mat labels, stats, centroids;",
            f"int count = cv::connectedComponentsWithStats(binary, labels, stats, "
            f"centroids, {p['connectivity']});",
        ]
        if p["mode"] == "labels":
            lines += [
                f"{d} = cv::Mat::zeros(binary.size(), CV_8UC3);",
                "cv::RNG rng(iteration_seed);",
            ]
        lines += [
            "for (int label = 1; label < count; ++label) {",
            f"    if (stats.at<int>(label, cv::CC_STAT_AREA) < {p['min_area']}) continue;",
        ]
        if p["mode"] == "labels":
            lines += [
                "    int b = rng.uniform(64,256), g = rng.uniform(64,256), r = "
                "rng.uniform(64,256);",
                f"    {d}.setTo(cv::Scalar(b,g,r), labels == label);",
            ]
        else:
            lines += [
                "    int x = stats.at<int>(label, cv::CC_STAT_LEFT), y = "
                "stats.at<int>(label, cv::CC_STAT_TOP);",
                "    int w = stats.at<int>(label, cv::CC_STAT_WIDTH), h = "
                "stats.at<int>(label, cv::CC_STAT_HEIGHT);",
                f"    cv::rectangle({d}, cv::Point(x,y), cv::Point(x+w-1,y+h-1), "
                f"cv::Scalar(0,255,120), 2);",
            ]
        return lines + ["}"]
    mode = "cv::RETR_" + p["mode"].upper() if kind == "find_contours" else "cv::RETR_EXTERNAL"
    method = (
        "cv::CHAIN_APPROX_" + p["method"].upper()
        if kind == "find_contours"
        else "cv::CHAIN_APPROX_SIMPLE"
    )
    lines += [
        "std::vector<std::vector<cv::Point>> contours;",
        f"cv::findContours(binary, contours, {mode}, {method});",
    ]
    if kind == "find_contours":
        return lines + [
            f"cv::drawContours({d}, contours, -1, cv::Scalar(0,255,128), {p['thickness']});"
        ]
    lines += ["for (const auto& contour : contours) {"]
    if kind == "convex_hull":
        lines += [
            "    if (contour.size() < 3) continue;",
            "    std::vector<cv::Point> hull; cv::convexHull(contour, hull);",
            f"    cv::drawContours({d}, "
            f"std::vector<std::vector<cv::Point>>{{hull}}, -1, "
            f"cv::Scalar(255,160,0), {p['thickness']});",
        ]
    else:
        lines += [
            "    double area = cv::contourArea(contour);",
            f"    if (area < {p['min_area']}) continue;",
        ]
        if kind == "moments":
            lines += [
                "    auto m = cv::moments(contour); if (std::abs(m.m00) < 1e-6) continue;",
                "    int cx = static_cast<int>(m.m10/m.m00), cy = static_cast<int>(m.m01/m.m00);",
                f"    cv::circle({d}, cv::Point(cx,cy), 4, cv::Scalar(0,200,255), -1);",
                f"    cv::drawContours({d}, "
                f"std::vector<std::vector<cv::Point>>{{contour}}, -1, "
                f"cv::Scalar(80,180,255), 1);",
                "    double angle = 0.5 * std::atan2(2*m.mu11/m.m00, m.mu20/m.m00-m.mu02/m.m00);",
                "    double length = std::max(12.0, std::sqrt(area)*0.35);",
                "    int dx = static_cast<int>(length*std::cos(angle)), dy = "
                "static_cast<int>(length*std::sin(angle));",
                f"    cv::line({d}, cv::Point(cx-dx,cy-dy), "
                f"cv::Point(cx+dx,cy+dy), cv::Scalar(0,255,180), 2);",
            ]
        elif kind == "bounding_rect":
            if p["kind"] == "rotated":
                lines += [
                    "    cv::Point2f points[4]; cv::minAreaRect(contour).points(points);",
                    "    std::vector<cv::Point> box; for (auto pt : points) "
                    "box.emplace_back(static_cast<int>(pt.x), "
                    "static_cast<int>(pt.y));",
                    f"    cv::drawContours({d}, "
                    f"std::vector<std::vector<cv::Point>>{{box}}, 0, "
                    f"cv::Scalar(255,80,80), {p['thickness']});",
                ]
            else:
                lines += [
                    "    auto rect = cv::boundingRect(contour);",
                    f"    cv::rectangle({d}, rect, cv::Scalar(255,80,80), {p['thickness']});",
                ]
        elif kind == "approx_poly":
            lines += [
                "    std::vector<cv::Point> polygon;",
                f"    cv::approxPolyDP(contour, polygon, {p['epsilon']} * "
                f"cv::arcLength(contour, true), true);",
                f"    cv::drawContours({d}, "
                f"std::vector<std::vector<cv::Point>>{{polygon}}, -1, "
                f"cv::Scalar(180,80,255), {p['thickness']});",
                f"    for (auto pt : polygon) cv::circle({d}, pt, 3, cv::Scalar(255,220,80), -1);",
            ]
        else:
            raise AssertionError(kind)
    return lines + ["}"]
