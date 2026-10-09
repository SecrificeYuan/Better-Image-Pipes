# Better Image Pipes：C++ 导出冻结范围

开发基线为公开仓库的 `baseline-20261010` 标签，提交 `bb10a15`，保留官方 v0.3.0 历史、MIT 许可证和当前中英双语源码。完整 Windows 安装目录备份位于 [基线 Release](https://github.com/SecrificeYuan/Better-Image-Pipes/releases/tag/baseline-20261010)，包含 ZIP、文件清单和 SHA-256 校验文件。

目标：新增 C++ 导出界面及 `POST /api/codegen/cpp`，生成独立 C++17 文件，覆盖全部 54 个内置 OpenCV 节点。批量输入、分支、多端口、类型转换、Unicode 路径、迭代和保存遵循现有节点执行语义。ZIP 使用 libarchive。错误快速终止；不支持节点明确阻止导出。现有 Python 生成器、节点实现、注册机制、工作流格式及桌面启动逻辑保持现有行为。

允许修改：

```text
backend/app/api/routes.py
frontend/src/features/code/CodePanel.tsx
frontend/src/hooks/useExecutionSocket.ts
frontend/src/store/graphStore.ts
frontend/src/i18n/en.json
frontend/src/i18n/zh-CN.json
frontend/package.json
frontend/package-lock.json
scripts/verify-localization.mjs
desktop/package.json
README.md
```

允许新增：

```text
backend/app/services/cpp_codegen/__init__.py
backend/app/services/cpp_codegen/compiler.py
backend/app/services/cpp_codegen/common.py
backend/app/services/cpp_codegen/io.py
backend/app/services/cpp_codegen/color.py
backend/app/services/cpp_codegen/filters.py
backend/app/services/cpp_codegen/analysis.py
backend/app/services/cpp_codegen/geometry.py
backend/app/services/cpp_codegen/math.py
backend/app/services/cpp_codegen/morphology.py
backend/app/services/cpp_codegen/clustering.py
backend/app/services/cpp_codegen/structure.py
backend/tests/test_codegen_cpp.py
backend/tests/test_codegen_cpp_native.py
backend/tests/helpers/cpp_codegen_cases.py
frontend/playwright.config.ts
frontend/e2e/code-export.spec.ts
.github/workflows/cpp-export.yml
docs/cpp-export.md
docs/cpp-export-plan.md
docs/baseline-manifest.json
scripts/verify-cpp-export-scope.py
```

`scripts/verify-cpp-export-scope.py` 以公开基线检查提交、工作区和未跟踪源码，清单之外的文件变化立即失败。验证产物放在忽略目录或系统临时目录。功能提交推送到 `feat/cpp-export`。

验收使用真实图像、编译器、服务、浏览器和安装包。Python/C++ 对照版本为 OpenCV 4.13.0，4.5.4 补充兼容检查；整数操作逐像素一致，浮点操作每通道最多 1 个灰度级误差；随机算法验证结构、参数、有效聚类及原生环境种子复现。最终构建 Windows 0.4.0 安装包，并从桌面程序实际导出、编译和运行下载文件。
