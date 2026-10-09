"""C++ literals and shared native image operations."""

import json
import re


def literal(value: str) -> str:
    """Use UTF-8 literals with C++-compatible JSON escapes."""
    escaped = json.dumps(value, ensure_ascii=False)
    return "u8" + re.sub(r"\\u00([0-9a-f]{2})", lambda m: f"\\{int(m[1], 16):03o}", escaped)


def odd(value: int) -> int:
    return value if value % 2 else value + 1


RUNTIME = r"""
#include <opencv2/opencv.hpp>
#include <algorithm>
#include <cmath>
#include <cctype>
#include <cstdint>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <limits>
#include <map>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;

void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}

cv::Mat read_image(const std::string& name) {
    std::ifstream file(fs::u8path(name), std::ios::binary);
    require(file.is_open(), "Cannot open image: " + name);
    std::vector<uchar> bytes((std::istreambuf_iterator<char>(file)), {});
    require(!file.bad() && !bytes.empty(), "Cannot read image: " + name);
    cv::Mat image = cv::imdecode(bytes, cv::IMREAD_UNCHANGED);
    require(!image.empty(), "Cannot decode image: " + name);
    return image;
}

cv::Mat as_gray(const cv::Mat& image) {
    if (image.channels() == 1) return image;
    cv::Mat result;
    cv::cvtColor(image, result, image.channels() == 4 ? cv::COLOR_BGRA2GRAY : cv::COLOR_BGR2GRAY);
    return result;
}

cv::Mat as_bgr(const cv::Mat& image) {
    if (image.channels() == 3) return image.clone();
    cv::Mat result;
    cv::cvtColor(image, result, image.channels() == 1 ? cv::COLOR_GRAY2BGR : cv::COLOR_BGRA2BGR);
    return result;
}

cv::Mat resize_to(const cv::Mat& image, cv::Size size, int interpolation = cv::INTER_LINEAR) {
    if (image.size() == size) return image;
    cv::Mat result;
    cv::resize(image, result, size, 0, 0, interpolation);
    return result;
}

void align_pair(cv::Mat& a, cv::Mat& b) {
    b = resize_to(b, a.size());
    if (a.channels() == 1 && b.channels() > 1) cv::cvtColor(a, a, cv::COLOR_GRAY2BGR);
    else if (a.channels() > 1 && b.channels() == 1) cv::cvtColor(b, b, cv::COLOR_GRAY2BGR);
    else if (a.channels() != b.channels()) {
        if (a.channels() == 4) cv::cvtColor(a, a, cv::COLOR_BGRA2BGR);
        if (b.channels() == 4) cv::cvtColor(b, b, cv::COLOR_BGRA2BGR);
        require(a.channels() == b.channels(), "Images must have compatible channel counts");
    }
}

cv::Mat trunc_u8(const cv::Mat& image) {
    cv::Mat floating;
    image.convertTo(floating, CV_64F);
    cv::Mat result(image.size(), CV_MAKETYPE(CV_8U, image.channels()));
    for (int y = 0; y < image.rows; ++y) {
        const double* src = floating.ptr<double>(y);
        uchar* dst = result.ptr<uchar>(y);
        for (int x = 0; x < image.cols * image.channels(); ++x) {
            require(std::isfinite(src[x]), "Non-finite image value");
            dst[x] = static_cast<uchar>(std::clamp(src[x], 0.0, 255.0));
        }
    }
    return result;
}

cv::Mat binary_image(const cv::Mat& image) {
    cv::Mat gray = as_gray(image), different, result;
    cv::inRange(gray, cv::Scalar::all(0), cv::Scalar::all(0), different);
    cv::Mat white;
    cv::inRange(gray, cv::Scalar::all(255), cv::Scalar::all(255), white);
    cv::bitwise_or(different, white, different);
    if (cv::countNonZero(different) == gray.rows * gray.cols) return gray;
    cv::threshold(gray, result, 0, 255, cv::THRESH_BINARY | cv::THRESH_OTSU);
    return result;
}

std::string timestamp() {
    std::time_t now = std::time(nullptr);
    std::tm local{};
#ifdef _WIN32
    require(localtime_s(&local, &now) == 0, "Cannot format local time");
#else
    require(localtime_r(&now, &local) != nullptr, "Cannot format local time");
#endif
    std::ostringstream text;
    text << std::put_time(&local, "%Y%m%d_%H%M%S");
    return text.str();
}

void replace_all(std::string& text, const std::string& from, const std::string& to) {
    size_t pos = 0;
    while ((pos = text.find(from, pos)) != std::string::npos) {
        text.replace(pos, from.size(), to); pos += to.size();
    }
}

std::string filename_for(std::string name, const std::string& stem, size_t index) {
    bool indexed = name.find("{filename}") != std::string::npos ||
        name.find("{time}") != std::string::npos || name.find("{index}") != std::string::npos;
    std::string safe_stem = fs::u8path(stem).stem().u8string();
    if (safe_stem.empty()) safe_stem = "image";
    replace_all(safe_stem, "/", "_"); replace_all(safe_stem, "\\", "_");
    replace_all(name, "{filename}", safe_stem);
    replace_all(name, "{time}", timestamp());
    replace_all(name, "{index}", std::to_string(index));
    name = fs::u8path(name).filename().u8string();
    require(!name.empty() && name != "." && name != "..", "Invalid output filename");
    if (index > 0 && !indexed) {
        auto path = fs::u8path(name);
        name = path.stem().u8string() + "_" + std::to_string(index) + path.extension().u8string();
    }
    return name;
}

std::vector<uchar> encode_image(const std::string& name, const cv::Mat& image) {
    auto suffix = fs::u8path(name).extension().u8string();
    require(!suffix.empty(), "Output filename requires an image extension: " + name);
    std::vector<uchar> bytes;
    require(cv::imencode(suffix, image, bytes), "Cannot encode image: " + name);
    return bytes;
}

void write_image(const fs::path& path, const cv::Mat& image) {
    auto bytes = encode_image(path.filename().u8string(), image);
    fs::create_directories(path.parent_path());
    std::ofstream file(path, std::ios::binary);
    require(file.is_open(), "Cannot create image: " + path.u8string());
    file.write(reinterpret_cast<const char*>(bytes.data()),
        static_cast<std::streamsize>(bytes.size()));
    file.close();
    require(!file.fail(), "Cannot write image: " + path.u8string());
}
"""
