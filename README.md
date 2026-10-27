# mimiTalk

深空之眼弥弥尔通讯聊天软件。用户接入 API 后可与 AI 角色对话，可在软件内编辑角色卡（提示词）。

本仓库是 **P3 alpha v0.1.2** 的源码快照；按 release 同步纪律，只包含程序本体，不含开发文档、测试与用户数据。

## 运行

需要 Python 3.12 与 Node.js。

```powershell
# 1. 安装后端依赖
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. 构建前端
cd web
npm install
npm run build
cd ..

# 3. 配置
copy config\p3.example.toml config\p3.toml
# 编辑 config\p3.toml，填写 [model] 的 base_url / api_key / model

# 4. 启动
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir . --host 127.0.0.1 --port 8000
```

打开 <http://127.0.0.1:8000/>。

> `scripts/start.ps1` 是 P3 工作区内的启动脚本，默认使用 `..\..\.venv`；在独立克隆的仓库中请用上面的命令，或把脚本里的 `$Venv` 改为仓库内的 `.venv`。

## 说明

- 非官方粉丝项目，与《深空之眼》权利人无关联。
- 软件本体不生成、不存储、不上传对话内容；回复由用户接入的第三方模型和用户编辑的提示词决定。
- 角色名称、头像、气泡、贴纸等素材版权归原权利人；本仓库仅用于粉丝向学习交流，不主张相关权利，如权利人提出异议将移除。
- 本仓库不含真实 API Key；`config/p3.example.toml` 为空白示例配置。
- 本仓库不含预编译便携包；如需运行包，请使用发布页或单独提供的产品包。
- 代码以 **MIT License** 发布，见 `LICENSE`；第三方资源见 `THIRD_PARTY_NOTICES.md`。
