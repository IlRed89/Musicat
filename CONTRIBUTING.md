# 🤝 Contributing to Musicat

Thank you for your interest in contributing to **Musicat**!  
We welcome pull requests, bug reports, feature suggestions, and documentation enhancements from DJs, audio developers, and music enthusiasts.

---

## 🛠️ Development Setup

### 1. Prerequisites
- **Python:** 3.11, 3.12, or 3.13 (64-bit recommended)
- **Git**
- Optional: Voidtools Everything (for local MFT search testing)
- Optional: VideoLAN VLC installed or VLC SDK DLLs in `vlc/` folder

### 2. Clone & Install Dependencies
```powershell
git clone https://github.com/IlRed89/Musicat.git
cd Musicat

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install requirements
pip install -r requirements.txt
```

### 3. Run Unit Tests
Before submitting any changes, verify that all unit tests pass:
```powershell
python -m unittest discover tests -v
```

---

## 📐 Coding Standards & Guidelines

To maintain code clarity and stability, all contributions must adhere to the following standards:

1. **Strict Type Hinting:**
   Always use Python's `typing` module (`Optional`, `Dict`, `List`, `Tuple`, `Union`, `Any`, `Callable`).
2. **Google Style Docstrings:**
   Every class, method, and standalone function must include docstrings formatted with `Args:`, `Returns:`, and `Raises:`.
3. **In-Line Documentation:**
   Add descriptive in-line comments explaining non-trivial logic (signal processing, FFT/Chroma calculations, regex token matching, thread-safe locks).
4. **Non-Destructive Tagging:**
   Tag editor operations must preserve existing fields unless explicitly modified by the user.

---

## 🚀 Submitting a Pull Request

1. Fork the repository and create a descriptive branch:
   ```powershell
   git checkout -b feature/your-feature-name
   ```
2. Make your changes, adhering to coding and testing standards.
3. Ensure all tests pass: `python -m unittest discover tests`.
4. Commit your changes with conventional commit messages:
   ```powershell
   git commit -m "feat(scrapers): add Beatport Pro streaming link extraction"
   ```
5. Push to your fork and submit a Pull Request to `main`.

Thank you for helping make Musicat the best open-source DJ cataloger! 🎧
