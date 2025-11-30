# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a FastAPI-based MCP (Model Context Protocol) server that wraps NeqSim, a Java-based process simulation library for oil & gas applications. The server exposes rigorous thermodynamic and process simulations as REST API endpoints for AI agents to optimize production parameters.

## Development Environment Setup

This project uses Nix flakes with `uv` for Python dependency management:

```bash
# Enter development environment (creates .venv and installs dependencies)
nix develop

# Or with direnv (automatically activates when entering directory)
direnv allow
```

The flake automatically:
- Creates a `.venv` virtual environment
- Activates it
- Syncs dependencies from `pyproject.toml` using `uv`

## Key Dependencies

- **NeqSim**: Java-based thermodynamic/process simulation library (wrapped via Python bindings)
- **FastAPI**: Web framework for the API server
- **Pydantic**: Request/response validation
- **uv**: Fast Python package installer and resolver

## Running the Server

```bash
# Start the FastAPI development server
uvicorn server:app --reload

# Or with specific host/port
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

## Architecture

### Single-File Application
Currently the entire server is in `server.py` - a simple FastAPI application with one simulation endpoint.

### NeqSim Import Pattern
NeqSim is a Java library accessed via JPype. Classes cannot be imported using standard Python `from...import` syntax. Instead, access them as attributes:

```python
import neqsim
ProcessSystem = neqsim.jneqsim.process.processmodel.ProcessSystem
Stream = neqsim.jneqsim.process.equipment.stream.Stream
# etc.
```

### Simulation Flow
The `/simulate_process` endpoint implements a complete oil stabilization process based on the NeqSim Colab example:

**Process Topology:**
1. **Well Stream** → Water Saturator → Temperature/Pressure Setter
2. **3-Stage Separation** (75 bara → 8.6 bara → 1.9 bara)
   - Oil heating between stages
   - Throttling valves for pressure control
3. **Gas Recompression System**
   - LP gas from 3rd stage compressed through 2 stages
   - Intercooling after each compression stage
   - Mixed with 1st stage gas
4. **Dew Point Control**
   - Cooling and final separation before export
   - LP liquids recycled to 3rd stage separator
5. **Export Gas Compression** (2-stage to 200 bara)

**Fluid Composition:**
- Rich well fluid with C1-C13+ hydrocarbons using Peng-Robinson EOS
- Includes TBP fractions for heavier components
- Water saturation included

**Results Provided:**
- TVP (True Vapor Pressure) of stabilized oil
- Cricondenbar of export gas
- Power consumption for all compressors
- Stable oil and export gas flow rates

### NeqSim Integration Pattern
This code uses NeqSim's **simplified Python API**:
```python
from neqsim.thermo import fluid
from neqsim.process import stream, separator, valve, compressor, etc.

# Create fluid
wellFluid = fluid('pr')  # Peng-Robinson EOS

# Build process
myStream = stream("name", wellFluid)
mySep = separator("name", myStream)

# Run
oilprocess = getProcess()
oilprocess.runAsThread()
```

**Important:** Use `clearProcess()` at the start to reset the global process state.

### Agent-Controllable Parameters
All process operating conditions are exposed via the API:
- Well conditions (pressure, temperature, flow rate)
- Separation stage pressures (3 stages)
- Heater/cooler temperatures (5 temperature specs)
- Compressor discharge pressures

## Project Requirements

- Python >=3.13
- Java runtime (required by NeqSim)
- Nix with flakes enabled (for development environment)
