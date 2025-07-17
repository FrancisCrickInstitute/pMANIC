# MANIC

## Developer Instructions (MacOS/Linux)

### Install Package/Project Manager

Download [uv](https://github.com/astral-sh/uv) (if not already downloaded):
```bash
# On macOS and Linux.
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Set up the virtual environment

1. Create the virtual environment (if not already created):
```bash
uv venv
```

2. Activate the virtual environment:
```bash
source .venv/bin/activate
```

3. Install the project dependencies:
```bash
uv sync
```

Add dependencies:
```bash
uv add package-name
```

Remove dependencies:
```bash
uv remove package-name
```

Run scripts:
```bash
uv run python your_script.py
```

### Run the project

There are two ways to run the project:

```bash
./run.sh
```

or

```bash
uv run python -m src.manic.main
```
