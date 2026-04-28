[app]

# Application title
title = FRIDAY Assistant

# Package name
package.name = friday

# Package domain
package.domain = com.friday.ai

# Source directory
source.dir = .

# Files to include
source.include_exts = py,png,jpg,kv,atlas,json
source.include_patterns = assets/*,.env
source.exclude_dirs = .git,.buildozer,__pycache__,bin,local_models,model_cache,uploads,New folder
source.exclude_patterns = *.pyc,*.pyo

# Version
version = 0.1

# Python/Kivy requirements
requirements = python3,kivy,plyer,pymupdf,numpy,openai,requests,charset-normalizer,python-dotenv,wikipedia,pypdf,pdfminer.six,pillow,pytesseract

# Screen orientation
orientation = portrait

# Fullscreen
fullscreen = 0

# -----------------------------
# Android Specific
# -----------------------------

# Permissions needed
android.permissions = INTERNET,RECORD_AUDIO,READ_EXTERNAL_STORAGE

# Android architectures
android.archs = arm64-v8a, armeabi-v7a

# Allow Android auto backup
android.allow_backup = True

# Debug build format
android.debug_artifact = apk

# -----------------------------
# Python-for-Android
# -----------------------------

p4a.branch = master

# -----------------------------
# Buildozer settings
# -----------------------------

[buildozer]

# Log level
log_level = 2

# Warn if running as root
warn_on_root = 1
