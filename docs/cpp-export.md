# C++ 导出

在「代码」面板选择 C++，点击「导出 C++」。程序生成并下载 `pipeline.cpp`，编辑器显示 C++ 语法高亮。修改流程、参数、随机种子或迭代次数后，重新生成即可下载最新代码。生成期间、流程运行期间和空流程的生成按钮禁用。

导出文件是独立 C++17 程序。输入文件清单、输出目录、种子和迭代次数集中在配置区；使用前将其中的路径调整为目标机器上的实际路径。输入路径支持中文、空格和引号，Windows 通过 Unicode 文件路径读取二进制数据后解码。无需保存节点也可以运行，终端显示各输出端口的图像尺寸。

## 编译运行

安装 OpenCV 开发库和 C++17 编译器。包含 ZIP 保存节点时，额外安装 libarchive 开发库。Linux 示例：

```sh
g++ -std=c++17 pipeline.cpp -o pipeline $(pkg-config --cflags --libs opencv4)
./pipeline
# 包含 ZIP 保存：
g++ -std=c++17 pipeline.cpp -o pipeline $(pkg-config --cflags --libs opencv4 libarchive)
```

Windows 使用 MSVC 的 `/std:c++17 /utf-8` 编译选项，配置 OpenCV 头文件、导入库和运行时 DLL；包含 ZIP 的程序还需配置 libarchive。可以用 vcpkg 安装这些开发依赖。程序使用 core、imgproc、imgcodecs 和 features2d 模块。

## 支持范围与执行语义

支持 54 个内置 OpenCV 节点：输入输出 4、颜色处理 13、滤波及阈值 9、分析 7、几何变换 4、图像运算 5、形态学 3、结构分析 7、颜色聚类 2。Custom Python、用户脚本、Albumentations、Annotations、随机亮度对比度和高斯噪声会在导出时定位到节点并阻止下载。

按拓扑顺序执行，每个节点及输出端口保存独立变量。绘制使用图像副本，保持其他分支的输入。图像读取节点的资产注册表在导出时展开为实际文件清单；最大输入批次数量决定批次长度，其他输入按批次索引取模。每次迭代的随机种子为基础种子加迭代索引。

保存支持 `{filename}`、`{time}`、`{index}` 模板，自动避开重名文件。ZIP 保存将同一输出目录的结果写入一个压缩包。读取、编码、写入、空输出或 OpenCV 算法失败会立即终止程序。导出时检查节点、参数类型和范围、端口、必要输入、重复连接、环和输入资源。导出的绝对路径需要在目标机器存在。

整数图像操作按逐像素一致验收；浮点操作允许每通道至多 1 个灰度级误差。连通域颜色与 K-Means 在同一原生环境中可复现，允许与 Python 的随机颜色及聚类中心不同。主色直方图按频数降序排列，频数相同时保持颜色编码顺序。

## 后端接口

```text
POST /api/codegen/cpp
请求：{ "graph": 工作流图, "seed": 0, "iteration_count": 1 }
响应：{ "code": 完整源码, "filename": "pipeline.cpp", "dependencies": ["opencv"] }
```

ZIP 流程的依赖包含 `libarchive`。图校验失败返回 HTTP 422，`detail` 包含 `message`、`node_id`、`node_type`。请求结构校验使用 FastAPI 标准的 422 字段定位。现有 Python 接口保持原有输出行为。

## 验证

`backend/tests/test_codegen_cpp_native.py` 使用真实样例图像、Python 节点执行实现、生成的 C++ 程序和本机编译器。涵盖 54 个节点、参数选项及有效边界、重复执行的种子复现、批量输入、分支、通道拆分合并、掩码、ZIP 解压和运行失败。

原生对照环境固定 Python/C++ OpenCV 4.13.0。兼容编译检查可单独使用 OpenCV 4.5.4：

```sh
cd backend
python -m pytest tests/test_codegen_cpp.py tests/test_codegen_cpp_native.py
# 使用系统 4.5.4 的 pkg-config 路径单独检查兼容性：
python -m pytest tests/test_codegen_cpp_native.py -k compatibility
```

前端：`npm run typecheck`、`npm run lint`、`npm run build`、`npm run test:e2e`。端到端测试启动真实后端和 Vite，使用 Chromium 和 Monaco，输出下载文件及中文界面截图。冻结范围：`uv run --project backend python scripts/verify-cpp-export-scope.py`。

libarchive 文件名处理遵循其 [文件名说明](https://github.com/libarchive/libarchive/wiki/Filenames) 和 [官方示例](https://github.com/libarchive/libarchive/wiki/Examples)，ZIP 写入使用 UTF-8 字符环境。

## 2026-10-10 验收记录

| 验证内容 | 结果 |
|---|---|
| Python/C++ OpenCV 4.13.0，54 个节点及 250 组参数 | 通过 |
| 后端校验、API、批量、分支、掩码、ZIP、失败及种子边界 | 29 项通过 |
| OpenCV 4.5.4 完整 54 节点流程编译及运行 | 通过 |
| 真实 Chromium、Monaco C++ 语法、双语、下载及过期状态 | 3 项通过 |
| 类型检查、ESLint、后端 Ruff、生产构建、双语及冻结范围 | 通过 |
| Windows 0.4.0 安装程序窗口启动 | 通过 |
| 打包后的 Windows 桌面程序：生成并下载 C++，实际运行流程 | 通过 |
| 桌面下载文件：WSL OpenCV 4.13.0 编译运行、两次迭代 | 通过 |

安装包：`ImagePipes-Setup-0.4.0.exe`，200282319 字节。SHA-256：

```text
54e337ab5d6d70e354ba2264188d12c661c4c1e3cab55293bfbc396b2f748790
```

[安装包与逐项验证报告](https://github.com/SecrificeYuan/Better-Image-Pipes/releases/tag/cpp-export-0.4.0)。完整文件备份另见基线 Release。
