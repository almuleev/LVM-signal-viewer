# LVM Signal Viewer

[English version](README.md)

[![Tests](https://github.com/almuleev/LVM-signal-viewer/actions/workflows/tests.yml/badge.svg)](https://github.com/almuleev/LVM-signal-viewer/actions/workflows/tests.yml)
[![Latest release](https://img.shields.io/github/v/release/almuleev/LVM-signal-viewer?sort=semver)](https://github.com/almuleev/LVM-signal-viewer/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform: Windows](https://img.shields.io/badge/platform-Windows-0078D6.svg)](#скачать)

Быстрый десктопный просмотрщик измерений LabVIEW: откройте файл, изучите сигналы и экспортируйте результаты за секунды.

![LVM Signal Viewer — режим времени](docs/assets/screenshot.png)

## Скачать

- Windows-версия: [Latest Release](https://github.com/almuleev/LVM-signal-viewer/releases/latest)
- Все релизные артефакты: [Releases](https://github.com/almuleev/LVM-signal-viewer/releases)
- Запуск из исходников: клонируйте репозиторий и запустите через Python.

## Скриншоты

Режим частоты (Hz) с FFT-спектром:

![Режим Hz / FFT](docs/assets/screenshot-hz.png)

Пустой стартовый экран:

![Пустой стартовый экран](docs/assets/empty-start.png)

> Скриншоты рендерятся из встроенного примера командой
> `python tools/capture_screenshots.py` — перезапустите её, чтобы обновить после изменений UI.

## Поддерживаемые форматы

- `.lvm` (LabVIEW Measurement)
- `.txt` (числовой текст с табуляцией)

Пока не поддерживаются как входные форматы:
- `.csv`
- `.xlsx` / `.xls`

Экспорт в CSV поддерживается для текущего видимого диапазона данных.

## Ключевые возможности

- Пустой стартовый режим с понятной точкой входа `Open file`.
- Поддержка LVM-файлов с несколькими заголовками и немонотонным временем по секциям.
- Панель видимости каналов с живым обновлением легенды.
- Слайдеры Timeline и zoom, а также числовые поля `Position (%)` и `Window (%)`.
- Режим времени и Hz-режим на основе FFT.
- Инструмент Probe для точных значений на видимых трассах.
- Профили производительности (`Fast`, `Balanced`, `Quality`) для слабых и мощных машин.
- Экспорт текущего графика в PNG.
- Экспорт текущего видимого диапазона в CSV.
- Локальный кэш подготовленных данных для более быстрого повторного открытия.

## Быстрый старт

### Вариант A: скачать и запустить (Windows)

1. Перейдите в [Latest Release](https://github.com/almuleev/LVM-signal-viewer/releases/latest).
2. Скачайте Windows-артефакт.
3. Запустите `LVM_Signal_Viewer.exe`.

### Вариант B: запуск из исходников

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Установите зависимости и запустите:

```bash
pip install -r requirements.txt
python lvm_viewer.py
```

Опциональный стартовый файл:

```bash
python lvm_viewer.py path\to\file.lvm
```

## Управление

- Воспроизведение: `Space`, `Left/Right`, `Home/End`
- Масштаб/детализация: `Up/Down`, слайдер `Detail`, `Window (%)`
- Позиция: слайдер `Timeline`, `Position (%)`
- Режимы: `A` для вкл./выкл. анимации, `M` для Time/Hz, `V` для Probe, `P` для профиля производительности
- Файл: кнопка `Open file` или `Ctrl+O` / `Cmd+O`
- Экспорт: кнопка `Save PNG` или `Ctrl+S`; кнопка `Save CSV` или `Ctrl+E`
- Probe: левый клик для установки, правый клик или `Esc` для очистки

## Ограничения

- Только десктопное GUI-приложение (Tkinter + Matplotlib).
- Парсер входных данных ожидает числовые столбцы, разделенные табуляцией, где первый числовой столбец - время.
- Для больших файлов первый разбор всё ещё может занимать заметное время до создания кэша.
- FFT-режим предназначен для быстрого просмотра, а не для лабораторного спектрального анализа.
- Входной парсер Excel/CSV пока не реализован.

## Roadmap

- Добавить опциональную поддержку CSV-входа с определением разделителя.
- Добавить опциональную поддержку Excel-входа после проработки и валидации парсера.
- Добавить больше тестов крайних случаев парсера и UI smoke-тесты.
- Добавить подписанный pipeline релизов для Windows.
- Добавить скриншоты/GIF руководства пользователя в `docs/assets/`.

## Документация

- Сборка и упаковка: [docs/build.md](docs/build.md)
- Рекомендуемые GitHub topics: [docs/github-topics.md](docs/github-topics.md)
- Процесс релиза: [docs/release-checklist.md](docs/release-checklist.md)
- Идеи продвижения: [docs/promotion.md](docs/promotion.md)

## Как внести вклад

Мы приветствуем вклад в проект. Начните с [CONTRIBUTING.md](CONTRIBUTING.md).

## Лицензия

MIT License. См. [LICENSE](LICENSE).
