# TrailForge

TrailForge is an API endpoint specifically designed for cryptocurrency trading, starting with HyperLiquid as the initial exchange of choice due to the personal preference of the developer. This project aims to evolve into a robust platform that supports over 100 exchanges, offering users a comprehensive UI to manage accounts and subaccounts seamlessly.

TrailForge will empower traders by providing tools to backtest personal strategies, optimize them using machine learning, and eventually incorporate a wide array of functionalities to become an indispensable asset in the hands of algorithmic traders. The vision is to create a powerful, "aspiring-to-be-complete" tool that caters to the dynamic needs of crypto traders.

The name *TrailForge* draws inspiration from the enduring trails carved by camels across the vast, unpredictable desert seas. Amidst uncertainty, volatility, and indecisiveness, a camel remains steadfast, forging ahead with unwavering determination—much like the resilience required in navigating the crypto markets.

## Technologies Used

### Core Technologies
- **Python**: Primary programming language, chosen for its extensive ecosystem of financial and data analysis libraries.
- **FastAPI**: Modern, high-performance web framework for building APIs, selected for its asynchronous capabilities and automatic documentation.
- **Polars**: High-performance DataFrame library, used instead of pandas for superior speed with time-series data and type safety.
- **ccxt**: Cryptocurrency trading library that provides a unified API for multiple exchanges, enabling exchange-agnostic trading logic.
- **Uvicorn**: ASGI server for running the FastAPI application with high performance.

### Data Storage
- **Parquet Files**: Columnar storage format for efficiency in storing and retrieving time-series financial data.
- **Structured Logging**: Custom logging implementation for both executed orders and signal tracking.

## Architectural Techniques

### Async-First Design
- Implemented with **asyncio** to handle I/O-bound operations efficiently.
- Asynchronous context manager (**asynccontextmanager**) for application lifecycle management.
- Thread pooling for CPU-bound operations via **asyncio.to_thread**.

### Signal Deduplication System
- **truthCompass** class implements a sophisticated signal deduplication mechanism that:
  - Tracks and filters duplicate trading signals based on input variables.
  - Implements time-to-live (TTL) functionality to automatically expire old signals for better storage/memory management.
  - Uses a dual-storage approach with raw signals and de-duplicated signals (DSR) for future case studying.

### Webhook-Based Architecture
- RESTful API endpoints receive trading signals from external systems.
- Standardized payload validation using Pydantic models.
- Event-driven design pattern where signals trigger appropriate trading actions.

### Trading Implementation
- Leveraged cryptocurrency futures trading via the HyperLiquid exchange.
- Symbol mapping system to translate between different naming conventions.
- Trade execution with proper error handling and result verification.
- Dynamic order sizing and leverage control over webhook, and algorithmically in the future.

### Security Considerations
- Credential management through secure user input prompts.
- Ethereum wallet integration (address and private key validation).