"""Native color clustering and palette helpers."""

TYPES = {"kmeans_colors", "dominant_colors_hist"}

RUNTIME = r'''
cv::Mat palette_strip(const std::vector<cv::Vec3b>& colors, int width, int height) {
    require(!colors.empty(), "Empty color palette");
    cv::Mat strip = cv::Mat::zeros(height, width, CV_8UC3);
    int segment = width / static_cast<int>(colors.size());
    for (size_t n = 0; n < colors.size(); ++n) {
        int x0 = static_cast<int>(n) * segment;
        int x1 = n + 1 == colors.size() ? width : x0 + segment;
        if (x1 > x0) strip.colRange(x0,x1).setTo(cv::Scalar(colors[n][0],colors[n][1],colors[n][2]));
    }
    return strip;
}
'''


def emit(kind, p, i, o):
    s, d = i["image"], o["image"]
    lines = [f"cv::Mat image = as_bgr({s});", "std::vector<cv::Vec3b> colors;"]
    if kind == "kmeans_colors":
        k = p["k"]
        lines += ["cv::Mat samples, labels, centers; image.reshape(1, image.rows*image.cols).convertTo(samples, CV_32F);",
                  "cv::theRNG().state = iteration_seed;",
                  f"cv::kmeans(samples, {k}, labels, cv::TermCriteria(cv::TermCriteria::EPS | cv::TermCriteria::MAX_ITER, 40, 1.0), {p['attempts']}, cv::KMEANS_PP_CENTERS, centers);",
                  "cv::Mat centers_u8 = trunc_u8(centers);",
                  f"std::vector<int> counts({k},0), order({k}); std::iota(order.begin(),order.end(),0);",
                  "for (int n = 0; n < labels.rows; ++n) ++counts[labels.at<int>(n)];",
                  "std::stable_sort(order.begin(),order.end(),[&](int a,int b){return counts[a] > counts[b];});",
                  "for (int n : order) colors.emplace_back(centers_u8.at<uchar>(n,0),centers_u8.at<uchar>(n,1),centers_u8.at<uchar>(n,2));",
                  "cv::Mat quantized(image.size(), CV_8UC3);",
                  "for (int y = 0; y < image.rows; ++y) for (int x = 0; x < image.cols; ++x) {",
                  "    int label = labels.at<int>(y*image.cols+x);",
                  "    quantized.at<cv::Vec3b>(y,x) = cv::Vec3b(centers_u8.at<uchar>(label,0),centers_u8.at<uchar>(label,1),centers_u8.at<uchar>(label,2));", "}"]
        if p["output"] == "quantized":
            return lines + [f"{d} = quantized;"]
        lines += [f"cv::Mat strip = palette_strip(colors, image.cols, {p['palette_height']});"]
        return lines + ([f"cv::vconcat(quantized, strip, {d});"] if p["output"] == "both" else [f"{d} = strip;"])
    bins, top = p["bins"], p["top_k"]
    lines += [f"double step = 256.0 / {bins};", f"std::vector<int> counts({bins**3},0), order({bins**3});",
              "for (int y = 0; y < image.rows; ++y) for (int x = 0; x < image.cols; ++x) {",
              "    auto pixel = image.at<cv::Vec3b>(y,x);",
              f"    int b = static_cast<int>(pixel[0]/step), g = static_cast<int>(pixel[1]/step), r = static_cast<int>(pixel[2]/step);",
              f"    ++counts[b+g*{bins}+r*{bins*bins}];", "}",
              "std::iota(order.begin(), order.end(), 0);",
              "std::stable_sort(order.begin(),order.end(),[&](int a,int b){return counts[a] > counts[b];});",
              f"for (int n = 0; n < {top}; ++n) {{",
              "    int code = order[n]; if (counts[code] == 0) continue;",
              f"    colors.emplace_back(static_cast<uchar>((code%{bins})*step+step/2), static_cast<uchar>(((code/{bins})%{bins})*step+step/2), static_cast<uchar>((code/{bins*bins})*step+step/2));", "}",
              "require(!colors.empty(), \"Empty dominant-color histogram\");",
              f"cv::Mat strip = palette_strip(colors, image.cols, {p['palette_height']});"]
    return lines + ([f"cv::vconcat(image, strip, {d});"] if p["output"] == "both" else [f"{d} = strip;"])
