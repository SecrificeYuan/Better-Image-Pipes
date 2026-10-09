"""Analysis emitters and histogram rendering."""

from .common import literal, odd

TYPES = {
    "adaptive_threshold",
    "distance_transform",
    "histogram_equalize",
    "draw_histogram",
    "normalize",
    "compare_hist",
    "blur_detect",
}

RUNTIME = r"""
cv::Mat hist_image(const cv::Mat& image) {
    if (image.depth() == CV_8U) return image;
    cv::Mat floating; image.convertTo(floating, CV_32F);
    double maximum = 0;
    if (image.depth() == CV_32F || image.depth() == CV_64F) {
        for (int y = 0; y < floating.rows; ++y) {
            float* row = floating.ptr<float>(y);
            for (int x = 0; x < floating.cols * floating.channels(); ++x) {
                if (!std::isfinite(row[x])) row[x] = 0;
                maximum = std::max(maximum, static_cast<double>(row[x]));
            }
        }
        if (maximum <= 1) floating *= 255;
    } else {
        double limit = image.depth() == CV_16U ? 65535.0 :
            image.depth() == CV_16S ? 32767.0 : image.depth() == CV_32S ? 2147483647.0 : 127.0;
        if (limit > 255) floating *= static_cast<float>(255.0 / limit);
    }
    return trunc_u8(floating);
}

cv::Mat histogram(const cv::Mat& image, int channel) {
    cv::Mat hist;
    int bins = 256; float range[] = {0,256}; const float* ranges[] = {range};
    cv::calcHist(&image, 1, &channel, cv::Mat(), hist, 1, &bins, ranges);
    return hist;
}

void draw_hist_bars(cv::Mat& canvas, const cv::Mat& hist, cv::Scalar color) {
    double peak; cv::minMaxLoc(hist, nullptr, &peak);
    if (peak <= 0) return;
    double scale = (canvas.rows - 1) / peak;
    int bin_width = std::max(1, canvas.cols / 256);
    for (int i = 0; i < 256; ++i) {
        int height = static_cast<int>(static_cast<double>(hist.at<float>(i)) * scale);
        if (height <= 0) continue;
        int x = i * canvas.cols / 256;
        cv::rectangle(canvas, cv::Point(x, canvas.rows - 1 - height),
            cv::Point(std::min(canvas.cols - 1, x + bin_width), canvas.rows - 1), color, -1);
    }
}
"""


def emit(kind, p, i, o):
    d = o["image"]
    if kind == "compare_hist":
        method = {
            "correlation": "CORREL",
            "chi_square": "CHISQR",
            "intersection": "INTERSECT",
            "bhattacharyya": "BHATTACHARYYA",
        }[p["method"]]
        return [
            f"cv::Mat ha = histogram(as_gray({i['image_a']}), 0), hb = "
            f"histogram(as_gray({i['image_b']}), 0);",
            "cv::normalize(ha, ha, 0, 1, cv::NORM_MINMAX); cv::normalize(hb, hb, "
            "0, 1, cv::NORM_MINMAX);",
            f"double score = cv::compareHist(ha, hb, cv::HISTCMP_{method});",
            "std::ostringstream text; text << std::fixed << std::setprecision(4);",
            f"text << {literal(p['method'] + ': ')} << score;",
            f"{d} = cv::Mat(160, 420, CV_8UC3, cv::Scalar::all(32));",
            f"cv::putText({d}, text.str(), cv::Point(20,90), "
            f"cv::FONT_HERSHEY_SIMPLEX, 0.8, cv::Scalar::all(220), 2, "
            f"cv::LINE_AA);",
        ]
    s = i["image"]
    if kind == "adaptive_threshold":
        method = "GAUSSIAN_C" if p["method"] == "gaussian" else "MEAN_C"
        return [
            f"cv::adaptiveThreshold(as_gray({s}), {d}, {p['maxval']}, "
            f"cv::ADAPTIVE_THRESH_{method}, cv::THRESH_{p['type'].upper()}, "
            f"{odd(p['block_size'])}, {p['c']});"
        ]
    if kind == "distance_transform":
        return [
            "cv::Mat distance, normalized;",
            f"cv::distanceTransform(as_gray({s}), distance, "
            f"cv::DIST_{p['distance'].upper()}, {p['mask_size']});",
            "cv::normalize(distance, normalized, 0, 255, cv::NORM_MINMAX);",
            f"{d} = trunc_u8(normalized);",
        ]
    if kind == "normalize":
        return [
            f"cv::Mat floating; {s}.convertTo(floating, CV_32F);",
            f"cv::normalize(floating, floating, {p['alpha']}, {p['beta']}, "
            f"cv::NORM_{p['norm_type'].upper()});",
            f"{d} = trunc_u8(floating);",
        ]
    if kind == "histogram_equalize":
        return [
            f"if ({s}.channels() == 1) cv::equalizeHist({s}, {d});",
            "else {",
            f"    cv::Mat ycc; cv::cvtColor({s}, ycc, cv::COLOR_BGR2YCrCb);",
            "    std::vector<cv::Mat> channels; cv::split(ycc, channels);",
            "    cv::equalizeHist(channels[0], channels[0]); cv::merge(channels, ycc);",
            f"    cv::cvtColor(ycc, {d}, cv::COLOR_YCrCb2BGR);",
            "}",
        ]
    if kind == "draw_histogram":
        return [
            f"cv::Mat image = hist_image({s});",
            f"{d} = cv::Mat({p['height']}, {p['width']}, CV_8UC3, cv::Scalar::all(24));",
            "for (double fraction : {0.25,0.5,0.75}) {",
            f"    int y = static_cast<int>({d}.rows * (1-fraction));",
            f"    cv::line({d}, cv::Point(0,y), cv::Point({d}.cols-1,y), cv::Scalar::all(40), 1);",
            "}",
            f"if ({str(p['mode'] == 'gray').lower()} || image.channels() == 1) {{",
            f"    draw_hist_bars({d}, histogram(as_gray(image), 0), cv::Scalar::all(230));",
            "} else {",
            "    if (image.channels() == 4) cv::cvtColor(image, image, cv::COLOR_BGRA2BGR);",
            "    std::vector<cv::Scalar> colors{{255,90,90}, {90,220,90}, {90,90,255}};",
            f"    for (int c = 0; c < 3; ++c) draw_hist_bars({d}, histogram(image, c), colors[c]);",
            "}",
        ]
    if kind == "blur_detect":
        lines = [
            f"cv::Mat lap; cv::Laplacian(as_gray({s}), lap, CV_64F, {odd(p['ksize'])});",
            "cv::Scalar mean, deviation; cv::meanStdDev(lap, mean, deviation);",
            "double score = deviation[0] * deviation[0];",
            f"bool sharp = score >= {p['threshold']};",
            'std::ostringstream text; text << std::fixed << std::setprecision(1) '
            '<< "focus=" << score << (sharp ? " (sharp)" : " (blurry)");',
            "cv::Scalar color = sharp ? cv::Scalar(80,220,120) : cv::Scalar(80,80,255);",
        ]
        if p["output"] == "score_card":
            lines += [
                f"{d} = cv::Mat(120,420,CV_8UC3,cv::Scalar::all(28));",
                f"cv::putText({d}, text.str(), cv::Point(16,70), "
                f"cv::FONT_HERSHEY_SIMPLEX, 0.75, color, 2, cv::LINE_AA);",
            ]
        else:
            lines += [
                f"{d} = as_bgr({s});",
                f"cv::rectangle({d}, cv::Point(8,8), "
                f"cv::Point(std::min({d}.cols-8,360),42), cv::Scalar::all(0), -1);",
                f"cv::putText({d}, text.str(), cv::Point(14,34), "
                f"cv::FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv::LINE_AA);",
            ]
        return lines
    raise AssertionError(kind)
