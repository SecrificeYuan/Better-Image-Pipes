"""Image I/O and ZIP archive generation."""

from .common import literal

TYPES = {"load_image", "blank_image", "save_image", "preview"}

ZIP_RUNTIME = r"""
#include <archive.h>
#include <archive_entry.h>
#include <clocale>

using ZipBuckets = std::map<std::string, std::map<std::string, std::vector<uchar>>>;

void add_zip_image(ZipBuckets& buckets, const std::string& directory,
                   const std::string& name, const cv::Mat& image) {
    auto& files = buckets[fs::absolute(fs::u8path(directory)).u8string()];
    auto path = fs::u8path(name); std::string unique = name; int index = 2;
    while (files.count(unique)) unique = path.stem().u8string() + "_" +
        std::to_string(index++) + path.extension().u8string();
    files.emplace(unique, encode_image(unique, image));
}

void write_zips(const ZipBuckets& buckets) {
#ifdef _WIN32
    require(std::setlocale(LC_CTYPE, ".UTF-8") != nullptr, "Cannot select UTF-8 locale");
#else
    require(std::setlocale(LC_CTYPE, "C.UTF-8") != nullptr, "Cannot select UTF-8 locale");
#endif
    for (const auto& bucket : buckets) {
        fs::path directory = fs::u8path(bucket.first); fs::create_directories(directory);
        auto path = directory / fs::u8path("results_" + timestamp() + ".zip");
        int index = 2;
        while (fs::exists(path)) path = directory / fs::u8path("results_" + timestamp() + "_" +
            std::to_string(index++) + ".zip");
        archive* writer = archive_write_new();
        require(writer != nullptr, "Cannot create ZIP writer");
        require(archive_write_set_format_zip(writer) == ARCHIVE_OK,
            "Cannot select ZIP format");
        require(archive_write_set_options(writer, "zip:compression=deflate") == ARCHIVE_OK,
            "Cannot configure ZIP compression");
#ifdef _WIN32
        require(archive_write_open_filename_w(writer, path.c_str()) == ARCHIVE_OK,
            "Cannot open ZIP: " + path.u8string());
#else
        require(archive_write_open_filename(writer, path.c_str()) == ARCHIVE_OK,
            "Cannot open ZIP: " + path.u8string());
#endif
        for (const auto& file : bucket.second) {
            archive_entry* entry = archive_entry_new2(writer);
            require(entry != nullptr, "Cannot create ZIP entry");
            archive_entry_set_pathname_utf8(entry, file.first.c_str());
            archive_entry_set_size(entry, static_cast<la_int64_t>(file.second.size()));
            archive_entry_set_filetype(entry, AE_IFREG); archive_entry_set_perm(entry, 0644);
            require(archive_write_header(writer, entry) == ARCHIVE_OK,
                "Cannot write ZIP header: " + file.first);
            require(archive_write_data(writer, file.second.data(), file.second.size()) ==
                static_cast<la_ssize_t>(file.second.size()),
                "Cannot write ZIP entry: " + file.first);
            archive_entry_free(entry);
        }
        require(archive_write_close(writer) == ARCHIVE_OK, "Cannot close ZIP");
        require(archive_write_free(writer) == ARCHIVE_OK, "Cannot release ZIP writer");
        std::cout << "saved " << path.u8string() << '\n';
    }
}
"""


def emit(kind, p, i, o):
    d = o["image"]
    if kind == "load_image":
        source = p["_cpp_source"]
        return [
            f"{d} = {source}_images.at(batch_index % {source}_images.size());",
            f"source_stem = fs::u8path({source}_paths.at(sample_index % "
            f"{source}_paths.size())).stem().u8string();",
        ]
    if kind == "blank_image":
        size = (
            f"{i['size_ref']}.size()"
            if "size_ref" in i
            else f"cv::Size({p['width']}, {p['height']})"
        )
        channels = {"gray": 1, "bgr": 3, "bgra": 4}[p["channels"]]
        return [f"{d} = cv::Mat({size}, CV_8UC{channels}, cv::Scalar::all({p['fill']}));"]
    if kind == "preview":
        return [f"{d} = {i['image']};"]
    if kind == "save_image":
        directory = p["_cpp_output"]
        lines = [
            f"auto name = filename_for({literal(p['filename'] or '{filename}_{index}.png')}, "
            "source_stem, sample_index);",
            "auto extension = fs::u8path(name).extension().u8string();",
            "std::transform(extension.begin(),extension.end(),extension.begin(),"
            "[](unsigned char c){return static_cast<char>(std::tolower(c));});",
            'if (extension != ".png" && extension != ".jpg" && extension != ".jpeg" '
            '&& extension != ".bmp" && extension != ".webp") '
            'name = fs::u8path(name).stem().u8string() + ".png";',
        ]
        if p["packaging"] == "zip":
            lines += [f"add_zip_image(zip_buckets, {directory}, name, {i['image']});"]
        else:
            lines += [
                f"auto path = fs::u8path({directory}) / fs::u8path(name);",
                "auto original = path; int collision = 2;",
                'while (fs::exists(path)) path = original.parent_path() / '
                'fs::u8path(original.stem().u8string() + "_" + std::to_string(collision++) '
                '+ original.extension().u8string());',
                f"write_image(path, {i['image']});",
                "std::cout << \"saved \" << path.u8string() << '\\n';",
            ]
        return lines + [f"{d} = {i['image']};"]
    raise AssertionError(kind)
