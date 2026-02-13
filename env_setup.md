# 环境配置说明

## 使用uv配置环境

### 1. 安装uv

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. 创建虚拟环境并安装依赖

```bash
# 创建虚拟环境
uv venv

# 激活虚拟环境
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# 安装依赖
uv pip install -e .
```

### 3. 配置API密钥

创建 `.env` 文件:

```bash
# 复制示例文件
cp .env.example .env
```

编辑 `.env` 文件,填入您的千问API密钥:

```
DASHSCOPE_API_KEY=your_actual_api_key_here
```

### 4. 运行示例

```bash
python example_usage.py
```

## 注意事项

- 确保 `question_bank.json` 文件存在于项目根目录
- API密钥可以从阿里云DashScope控制台获取
- 如果遇到导入错误,确保已激活虚拟环境

