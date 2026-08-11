import os
import json
import zipfile
import io
import shutil
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from jinja2 import Template
from pydantic import BaseModel
import uvicorn

# ==================== 配置与配置记忆 ====================
DEFAULT_JSON_DIR = os.path.abspath("./strategies")
CONFIG_FILE = os.path.abspath("./AlphaManager_config.json")


def load_config() -> dict:
    """读取配置文件"""
    config = {
        "last_dir": DEFAULT_JSON_DIR,
        "theme": "light"
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    last_dir = data.get("last_dir")
                    if last_dir and os.path.exists(last_dir):
                        config["last_dir"] = last_dir
                    theme = data.get("theme")
                    if theme in ["light", "dark"]:
                        config["theme"] = theme
        except Exception:
            pass
    return config


def save_config(config_data: dict):
    """保存配置信息（目录与主题）"""
    try:
        current_config = load_config()
        current_config.update(config_data)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(current_config, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


app = FastAPI(title="量化 JSON 因子阅读器")

# ==================== 前端 HTML / CSS / JS 模板 ====================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN" data-theme="{{ theme }}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AlphaMaster - 量化因子阅读与分析平台</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=PingFang+SC:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        /* 主题变量 */
        :root[data-theme="dark"] {
            --bg-color: #0b0f19;
            --card-bg: #111827;
            --card-border: #1f2937;
            --card-hover-border: #00f2fe;
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
            --input-bg: #0d1322;
            --input-border: #243048;
            --input-focus: #00f2fe;
            --header-bg: #151e32;
            --table-hover: #172033;

            --accent-cyan: #00f2fe;
            --accent-blue: #3b82f6;
            --badge-symbol-bg: rgba(0, 242, 254, 0.12);
            --badge-symbol-text: #38ef7d;
            --badge-tf-bg: rgba(59, 130, 246, 0.15);
            --badge-tf-text: #60a5fa;
            --badge-score-bg: rgba(245, 158, 11, 0.15);
            --badge-score-text: #fbbf24;
            --glow-shadow: 0 0 15px rgba(0, 242, 254, 0.15);
        }

        :root[data-theme="light"] {
            --bg-color: #f4f6f9;
            --card-bg: #ffffff;
            --card-border: #e5e7eb;
            --card-hover-border: #3b82f6;
            --text-main: #1f2937;
            --text-muted: #6b7280;
            --input-bg: #f9fafb;
            --input-border: #d1d5db;
            --input-focus: #3b82f6;
            --header-bg: #f3f4f6;
            --table-hover: #f9fafb;

            --accent-cyan: #0284c7;
            --accent-blue: #2563eb;
            --badge-symbol-bg: #e0f2fe;
            --badge-symbol-text: #0369a1;
            --badge-tf-bg: #dbeafe;
            --badge-tf-text: #1d4ed8;
            --badge-score-bg: #fef3c7;
            --badge-score-text: #b45309;
            --glow-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }

        * { box-sizing: border-box; transition: background-color 0.25s, border-color 0.25s, color 0.25s; }
        body { 
            font-family: 'PingFang SC', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
            margin: 0; 
            padding: 24px; 
            background-color: var(--bg-color); 
            color: var(--text-main);
            min-height: 100vh;
        }

        /* 顶部 Header */
        .header-title { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
        .brand { display: flex; align-items: center; gap: 12px; }
        .brand-logo {
            width: 38px; height: 38px;
            background: linear-gradient(135deg, var(--accent-cyan), var(--accent-blue));
            border-radius: 10px; display: flex; align-items: center; justify-content: center;
            font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 20px; color: #fff;
        }
        .brand-text h1 { margin: 0; font-size: 20px; font-weight: 700; }
        .brand-text p { margin: 2px 0 0 0; font-size: 12px; color: var(--text-muted); }

        .theme-toggle-btn {
            background: var(--card-bg); border: 1px solid var(--card-border); color: var(--text-main);
            padding: 8px 14px; border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: 500;
            display: flex; align-items: center; gap: 6px;
        }
        .theme-toggle-btn:hover { border-color: var(--accent-cyan); }

        /* 卡片容器 */
        .panel { 
            background: var(--card-bg); padding: 16px 20px; border-radius: 12px; 
            border: 1px solid var(--card-border); margin-bottom: 16px; 
        }

        /* 工具栏与筛选 */
        .toolbar { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
        .toolbar label { font-weight: 600; font-size: 13px; color: var(--text-muted); }
        .path-input { 
            flex: 1; min-width: 300px; padding: 9px 14px; border: 1px solid var(--input-border); 
            border-radius: 8px; font-size: 13px; background: var(--input-bg); color: var(--text-main);
            font-family: 'JetBrains Mono', monospace;
        }
        .path-input:focus { outline: none; border-color: var(--input-focus); }

        .filter-bar { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
        .filter-group { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-muted); }
        .filter-group input, .filter-group select { 
            padding: 7px 10px; border: 1px solid var(--input-border); border-radius: 6px; 
            font-size: 13px; background: var(--input-bg); color: var(--text-main);
        }
        .filter-group input[type="number"] { width: 90px; }

        .btn { 
            background: linear-gradient(135deg, #2563eb, #1d4ed8); color: white; border: none; 
            padding: 8px 16px; border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: 500; 
            text-decoration: none; display: inline-flex; align-items: center; gap: 6px;
        }
        .btn:hover { opacity: 0.9; }
        .btn-success { background: linear-gradient(135deg, #10b981, #059669); }
        .btn-secondary { background: var(--input-bg); color: var(--text-main); border: 1px solid var(--input-border); }
        .btn-danger { background: rgba(239, 68, 68, 0.1); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3); }
        .btn-danger:hover { background: #ef4444; color: white; }
        .btn-sm { padding: 5px 10px; font-size: 12px; border-radius: 6px; }

        /* 表格容器 */
        .table-container { background: var(--card-bg); border-radius: 12px; border: 1px solid var(--card-border); overflow: hidden; margin-top: 16px; }
        table { width: 100%; border-collapse: collapse; text-align: left; font-size: 13px; }
        th, td { padding: 12px 14px; border-bottom: 1px solid var(--card-border); vertical-align: top; }
        th { background-color: var(--header-bg); color: var(--text-muted); font-weight: 600; white-space: nowrap; font-size: 12px; text-transform: uppercase; }
        tr:hover { background-color: var(--table-hover); }

        /* 单元格交互框 */
        .file-name-cell { display: flex; flex-direction: column; gap: 4px; }
        .file-name-cell input { 
            font-size: 13px; padding: 6px 10px; border: 1px solid var(--input-border); 
            border-radius: 6px; width: 100%; background: var(--input-bg); color: var(--text-main);
            font-family: 'JetBrains Mono', monospace;
        }
        .file-name-cell input:focus { border-color: var(--input-focus); outline: none; }

        .badge { display: inline-block; padding: 3px 10px; border-radius: 6px; font-size: 12px; font-weight: 600; white-space: nowrap; font-family: 'JetBrains Mono', monospace; }
        .badge-score { background: var(--badge-score-bg); color: var(--badge-score-text); }
        .badge-symbol { background: var(--badge-symbol-bg); color: var(--badge-symbol-text); }
        .badge-tf { background: var(--badge-tf-bg); color: var(--badge-tf-text); }

        .dataset-input { 
            width: 100%; font-family: 'JetBrains Mono', monospace; font-size: 12px; 
            padding: 6px 10px; border: 1px solid var(--input-border); border-radius: 6px; 
            background: var(--input-bg); color: var(--text-main);
        }
        .dataset-input:focus { border-color: var(--input-focus); outline: none; }

        .formula-text { 
            font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--accent-cyan); 
            background: var(--input-bg); padding: 8px 10px; border-radius: 6px; border: 1px solid var(--card-border);
            max-width: 320px; word-break: break-all; line-height: 1.4;
        }

        textarea.note-input { 
            width: 100%; min-height: 60px; padding: 8px 10px; border: 1px solid var(--input-border); 
            border-radius: 6px; resize: vertical; font-family: inherit; font-size: 13px; 
            background: var(--input-bg); color: var(--text-main);
        }
        textarea.note-input:focus { border-color: var(--input-focus); outline: none; }

        .action-btns { display: flex; flex-direction: column; gap: 6px; justify-content: center; }
        .status-tag { font-size: 11px; color: var(--text-muted); margin-top: 4px; }
        .stats-counter { font-size: 13px; color: var(--text-muted); margin-left: auto; font-weight: normal; }
    </style>
</head>
<body>

    <!-- 顶栏标题 -->
    <div class="header-title">
        <div class="brand">
            <div class="brand-logo">α</div>
            <div class="brand-text">
                <h1>AlphaMaster 因子管理中心</h1>
                <p>基于深度量化因子搜索与挖掘框架</p>
            </div>
        </div>
        <button class="theme-toggle-btn" onclick="toggleTheme()">
            <span id="theme-icon">{% if theme == 'dark' %}🌙{% else %}☀️{% endif %}</span>
            <span id="theme-text">{% if theme == 'dark' %}暗黑模式{% else %}日间模式{% endif %}</span>
        </button>
    </div>

    <!-- 目录路径选择（自动保持） -->
    <div class="panel toolbar">
        <label for="dir_path">读取目录：</label>
        <input type="text" id="dir_path" class="path-input" value="{{ current_dir }}" placeholder="请输入因子 JSON 文件的绝对路径">
        <button class="btn" onclick="loadDirectory()">加载文件夹</button>
        <a href="#" class="btn btn-success" onclick="downloadZip(event)">📦 批量打包下载 (.zip)</a>
    </div>

    <!-- 筛选面板 -->
    <div class="panel">
        <div class="filter-bar">
            <div class="filter-group">
                <span>🔍 搜索：</span>
                <input type="text" id="search-kw" placeholder="文件名/代码/公式/路径/笔记..." oninput="filterAndSort()">
            </div>

            <div class="filter-group">
                <span>⏱️ 周期：</span>
                <select id="filter-tf" onchange="filterAndSort()">
                    <option value="">全部周期</option>
                    {% for tf in timeframes %}
                    <option value="{{ tf }}">{{ tf }}</option>
                    {% endfor %}
                </select>
            </div>

            <div class="filter-group">
                <span>📈 得分：</span>
                <input type="number" id="filter-min-score" step="0.1" placeholder="最小值" oninput="filterAndSort()">
                <span>-</span>
                <input type="number" id="filter-max-score" step="0.1" placeholder="最大值" oninput="filterAndSort()">
            </div>

            <div class="filter-group">
                <span>⇅ 排序：</span>
                <select id="sort-by" onchange="filterAndSort()">
                    <option value="filename-asc">文件名 (升序 A-Z)</option>
                    <option value="filename-desc">文件名 (降序 Z-A)</option>
                    <option value="score-desc">得分 (从高到低)</option>
                    <option value="score-asc">得分 (从低到高)</option>
                    <option value="symbol-asc">品种 (A-Z)</option>
                </select>
            </div>

            <button class="btn btn-secondary btn-sm" onclick="resetFilters()">重置</button>

            <div class="stats-counter" id="stats-counter">
                共计 {{ items|length }} 条记录
            </div>
        </div>

        <!-- 表格部分 -->
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th style="width: 18%;">文件名 (实时重命名)</th>
                        <th style="width: 6%;">品种</th>
                        <th style="width: 6%;">周期</th>
                        <th style="width: 8%;">最优得分</th>
                        <th style="width: 20%;">数据集路径 (data_file)</th>
                        <th style="width: 20%;">因子公式 (formula)</th>
                        <th style="width: 15%;">笔记 (.txt)</th>
                        <th style="width: 7%; text-align: center;">操作</th>
                    </tr>
                </thead>
                <tbody id="data-tbody">
                    {% for item in items %}
                    <tr class="data-row" 
                        data-filename="{{ item.filename }}" 
                        data-symbol="{{ item.symbol }}" 
                        data-timeframe="{{ item.timeframe }}" 
                        data-score="{{ item.best_score_num }}"
                        data-datafile="{{ item.data_file }}"
                        data-formula="{{ item.formula_decoded }}"
                        data-note="{{ item.note_content }}">
                        <td>
                            <div class="file-name-cell">
                                <input type="text" id="fn-input-{{ loop.index }}" 
                                       value="{{ item.filename }}"
                                       data-current-name="{{ item.filename }}"
                                       oninput="autoRenameFile(this, 'fn-status-{{ loop.index }}')">
                                <div class="status-tag" id="fn-status-{{ loop.index }}">已同步</div>
                            </div>
                        </td>
                        <td><span class="badge badge-symbol">{{ item.symbol }}</span></td>
                        <td><span class="badge badge-tf">{{ item.timeframe }}</span></td>
                        <td><span class="badge badge-score">{{ item.best_score_str }}</span></td>
                        <td>
                            <input type="text" class="dataset-input" 
                                   value="{{ item.data_file }}" 
                                   placeholder="parquet 路径..."
                                   oninput="saveDataFile(this, 'df-status-{{ loop.index }}')">
                            <div class="status-tag" id="df-status-{{ loop.index }}">已同步</div>
                        </td>
                        <td><div class="formula-text">{{ item.formula_decoded }}</div></td>
                        <td>
                            <textarea class="note-input" 
                                      placeholder="输入因子备注..." 
                                      oninput="saveNote(this, 'status-{{ loop.index }}')">{{ item.note_content }}</textarea>
                            <div class="status-tag" id="status-{{ loop.index }}">已就绪</div>
                        </td>
                        <td>
                            <div class="action-btns">
                                <button class="btn btn-sm btn-secondary" onclick="copyFile(this)">📋 复制</button>
                                <button class="btn btn-sm btn-danger" onclick="deleteFile(this)">🗑️ 删除</button>
                            </div>
                        </td>
                    </tr>
                    {% else %}
                    <tr id="no-data-row">
                        <td colspan="8" style="text-align: center; color: var(--text-muted); padding: 40px;">
                            未在指定目录找到 JSON 因子文件，请检查路径。
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <script>
        async function toggleTheme() {
            const currentTheme = document.documentElement.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', newTheme);
            updateThemeUI(newTheme);

            // 保存主题设置到后端的配置文件中
            try {
                await fetch('/api/save_theme', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ theme: newTheme })
                });
            } catch (e) {
                console.error("保存主题属性配置失败", e);
            }
        }

        function updateThemeUI(theme) {
            const icon = document.getElementById('theme-icon');
            const text = document.getElementById('theme-text');
            if (theme === 'dark') {
                icon.innerText = '🌙'; text.innerText = '暗黑模式';
            } else {
                icon.innerText = '☀️'; text.innerText = '日间模式';
            }
        }

        let debounceTimers = {};

        // 1. 实时重命名逻辑 (防抖 600ms，无需确认)
        function autoRenameFile(inputElem, statusId) {
            const statusElem = document.getElementById(statusId);
            const row = inputElem.closest('tr');
            const oldFilename = inputElem.dataset.currentName;
            const newFilename = inputElem.value.trim();

            if (!newFilename || oldFilename === newFilename) {
                statusElem.innerText = "已同步";
                statusElem.style.color = "var(--text-muted)";
                return;
            }

            statusElem.innerText = "修改中...";
            statusElem.style.color = "#f59e0b";

            const key = "rename_" + oldFilename;
            if (debounceTimers[key]) clearTimeout(debounceTimers[key]);

            debounceTimers[key] = setTimeout(async () => {
                const dirPath = document.getElementById('dir_path').value;
                try {
                    const res = await fetch('/api/rename_file', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            dir_path: dirPath,
                            old_filename: oldFilename,
                            new_filename: newFilename
                        })
                    });
                    const data = await res.json();
                    if (res.ok) {
                        statusElem.innerText = "已保存";
                        statusElem.style.color = "#10b981";
                        // 更新 DOM 状态
                        const actualNewName = data.new_filename || newFilename;
                        inputElem.dataset.currentName = actualNewName;
                        row.dataset.filename = actualNewName;
                        inputElem.value = actualNewName;
                    } else {
                        statusElem.innerText = data.detail || "重命名失败";
                        statusElem.style.color = "#ef4444";
                    }
                } catch (e) {
                    statusElem.innerText = "网络错误";
                    statusElem.style.color = "#ef4444";
                }
            }, 600);
        }

        // 2. 实时保存数据集路径 (data_file -> json)
        function saveDataFile(inputElem, statusId) {
            const statusElem = document.getElementById(statusId);
            const row = inputElem.closest('tr');
            const filename = row.dataset.filename;

            statusElem.innerText = "修改中...";
            statusElem.style.color = "#f59e0b";

            const key = "df_" + filename;
            if (debounceTimers[key]) clearTimeout(debounceTimers[key]);

            debounceTimers[key] = setTimeout(async () => {
                const dirPath = document.getElementById('dir_path').value;
                try {
                    const res = await fetch('/api/update_data_file', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            dir_path: dirPath,
                            filename: filename,
                            data_file: inputElem.value
                        })
                    });
                    if (res.ok) {
                        statusElem.innerText = "已保存至 JSON";
                        statusElem.style.color = "#10b981";
                        row.dataset.datafile = inputElem.value;
                    } else {
                        statusElem.innerText = "保存失败";
                        statusElem.style.color = "#ef4444";
                    }
                } catch (e) {
                    statusElem.innerText = "网络错误";
                    statusElem.style.color = "#ef4444";
                }
            }, 500);
        }

        // 3. 实时保存笔记 (.txt)
        function saveNote(textarea, statusId) {
            const statusElem = document.getElementById(statusId);
            const row = textarea.closest('tr');
            const filename = row.dataset.filename;

            statusElem.innerText = "保存中...";
            statusElem.style.color = "#f59e0b";

            const key = "note_" + filename;
            if (debounceTimers[key]) clearTimeout(debounceTimers[key]);

            debounceTimers[key] = setTimeout(async () => {
                const dirPath = document.getElementById('dir_path').value;
                try {
                    const res = await fetch('/api/save_note', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            dir_path: dirPath,
                            filename: filename,
                            content: textarea.value
                        })
                    });
                    if (res.ok) {
                        statusElem.innerText = "已保存";
                        statusElem.style.color = "#10b981";
                        row.dataset.note = textarea.value;
                    } else {
                        statusElem.innerText = "保存失败";
                        statusElem.style.color = "#ef4444";
                    }
                } catch (e) {
                    statusElem.innerText = "网络错误";
                    statusElem.style.color = "#ef4444";
                }
            }, 500);
        }

        // 复制文件
        async function copyFile(btnElem) {
            const row = btnElem.closest('tr');
            const filename = row.dataset.filename;
            const dirPath = document.getElementById('dir_path').value;
            try {
                const res = await fetch('/api/copy_file', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ dir_path: dirPath, filename: filename })
                });
                if (res.ok) {
                    loadDirectory();
                } else {
                    const data = await res.json();
                    alert("复制失败: " + data.detail);
                }
            } catch (e) { alert("请求异常: " + e); }
        }

        // 删除文件
        async function deleteFile(btnElem) {
            const row = btnElem.closest('tr');
            const filename = row.dataset.filename;
            if (!confirm(`⚠️ 确定删除文件 "${filename}" 吗？\\n对应 .txt 备注也将同步删除！`)) return;

            const dirPath = document.getElementById('dir_path').value;
            try {
                const res = await fetch('/api/delete_file', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ dir_path: dirPath, filename: filename })
                });
                if (res.ok) {
                    loadDirectory();
                } else {
                    const data = await res.json();
                    alert("删除失败: " + data.detail);
                }
            } catch (e) { alert("请求异常: " + e); }
        }

        // 动态筛选与排序
        function filterAndSort() {
            const kw = document.getElementById('search-kw').value.toLowerCase().trim();
            const tf = document.getElementById('filter-tf').value;
            const minScoreVal = parseFloat(document.getElementById('filter-min-score').value);
            const maxScoreVal = parseFloat(document.getElementById('filter-max-score').value);
            const sortBy = document.getElementById('sort-by').value;

            const tbody = document.getElementById('data-tbody');
            const rows = Array.from(tbody.querySelectorAll('tr.data-row'));

            let visibleCount = 0;

            rows.forEach(row => {
                const filename = (row.dataset.filename || '').toLowerCase();
                const symbol = (row.dataset.symbol || '').toLowerCase();
                const rowTf = row.dataset.timeframe || '';
                const score = parseFloat(row.dataset.score || -999999);
                const datafile = (row.dataset.datafile || '').toLowerCase();
                const formula = (row.dataset.formula || '').toLowerCase();
                const note = (row.dataset.note || '').toLowerCase();

                const matchKw = !kw || filename.includes(kw) || symbol.includes(kw) || datafile.includes(kw) || formula.includes(kw) || note.includes(kw);
                const matchTf = !tf || rowTf === tf;
                const matchMinScore = isNaN(minScoreVal) || score >= minScoreVal;
                const matchMaxScore = isNaN(maxScoreVal) || score <= maxScoreVal;

                if (matchKw && matchTf && matchMinScore && matchMaxScore) {
                    row.style.display = '';
                    visibleCount++;
                } else {
                    row.style.display = 'none';
                }
            });

            rows.sort((a, b) => {
                if (sortBy === 'filename-asc') return a.dataset.filename.localeCompare(b.dataset.filename, undefined, {numeric: true});
                if (sortBy === 'filename-desc') return b.dataset.filename.localeCompare(a.dataset.filename, undefined, {numeric: true});
                if (sortBy === 'score-desc') return parseFloat(b.dataset.score || 0) - parseFloat(a.dataset.score || 0);
                if (sortBy === 'score-asc') return parseFloat(a.dataset.score || 0) - parseFloat(b.dataset.score || 0);
                if (sortBy === 'symbol-asc') return a.dataset.symbol.localeCompare(b.dataset.symbol);
                return 0;
            });

            rows.forEach(row => tbody.appendChild(row));
            document.getElementById('stats-counter').innerText = `显示 ${visibleCount} / 共 ${rows.length} 条记录`;
        }

        function resetFilters() {
            document.getElementById('search-kw').value = '';
            document.getElementById('filter-tf').value = '';
            document.getElementById('filter-min-score').value = '';
            document.getElementById('filter-max-score').value = '';
            document.getElementById('sort-by').value = 'filename-asc';
            filterAndSort();
        }

        function loadDirectory() {
            const dirPath = document.getElementById('dir_path').value;
            window.location.href = "/?dir=" + encodeURIComponent(dirPath);
        }

        function downloadZip(e) {
            e.preventDefault();
            const dirPath = document.getElementById('dir_path').value;
            window.location.href = "/api/download_zip?dir_path=" + encodeURIComponent(dirPath);
        }

        window.onload = function() {
            filterAndSort();
        };
    </script>
</body>
</html>
"""


# ==================== Pydantic 请求结构 ====================
class SaveThemeReq(BaseModel):
    theme: str


class SaveNoteReq(BaseModel):
    dir_path: str
    filename: str
    content: str


class UpdateDataFileReq(BaseModel):
    dir_path: str
    filename: str
    data_file: str


class RenameReq(BaseModel):
    dir_path: str
    old_filename: str
    new_filename: str


class FileActionReq(BaseModel):
    dir_path: str
    filename: str


# ==================== 后端 API 路由 ====================

@app.get("/", response_class=HTMLResponse)
async def index(dir: Optional[str] = None):
    config = load_config()

    # 如果 URL 传入了 dir，且存在，则更新记忆；否则使用配置中的路径
    if dir and os.path.exists(dir) and os.path.isdir(dir):
        target_dir = os.path.abspath(dir)
        save_config({"last_dir": target_dir})
    else:
        target_dir = config["last_dir"]

    current_theme = config.get("theme", "light")

    items = []
    timeframes = set()

    if not os.path.exists(target_dir):
        try:
            os.makedirs(target_dir, exist_ok=True)
        except Exception:
            pass

    if os.path.exists(target_dir) and os.path.isdir(target_dir):
        files = [f for f in os.listdir(target_dir) if f.lower().endswith('.json')]
        files.sort()

        for f in files:
            file_path = os.path.join(target_dir, f)
            txt_path = os.path.splitext(file_path)[0] + ".txt"

            symbol = "-"
            timeframe = "-"
            best_score_num = -999999.0
            best_score_str = "-"
            data_file = "-"
            formula_decoded = "-"

            try:
                with open(file_path, "r", encoding="utf-8") as jf:
                    data = json.load(jf)
                    symbol = str(data.get("symbol", "-"))
                    timeframe = str(data.get("timeframe", "-"))
                    if timeframe != "-":
                        timeframes.add(timeframe)

                    score_val = data.get("best_score", None)
                    if score_val is not None and isinstance(score_val, (int, float)):
                        best_score_num = float(score_val)
                        best_score_str = f"{best_score_num:.4f}"
                    else:
                        best_score_str = str(score_val) if score_val is not None else "-"

                    data_file = str(data.get("data_file", ""))
                    formula_decoded = str(data.get("formula_decoded", "-"))
            except Exception as e:
                formula_decoded = f"[解析 JSON 失败: {str(e)}]"

            note_content = ""
            if os.path.exists(txt_path):
                try:
                    with open(txt_path, "r", encoding="utf-8") as tf:
                        note_content = tf.read()
                except Exception:
                    pass

            items.append({
                "filename": f,
                "symbol": symbol,
                "timeframe": timeframe,
                "best_score_num": best_score_num,
                "best_score_str": best_score_str,
                "data_file": data_file,
                "formula_decoded": formula_decoded,
                "note_content": note_content
            })

    jinja_template = Template(HTML_TEMPLATE)
    return jinja_template.render(
        current_dir=target_dir,
        theme=current_theme,
        items=items,
        timeframes=sorted(list(timeframes))
    )


@app.post("/api/save_theme")
async def save_theme(req: SaveThemeReq):
    if req.theme not in ["light", "dark"]:
        raise HTTPException(status_code=400, detail="非法的主题属性")
    save_config({"theme": req.theme})
    return {"status": "success"}


@app.post("/api/save_note")
async def save_note(req: SaveNoteReq):
    if not os.path.exists(req.dir_path):
        raise HTTPException(status_code=400, detail="目录不存在")

    base_name = os.path.splitext(req.filename)[0]
    txt_path = os.path.join(req.dir_path, base_name + ".txt")

    try:
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(req.content)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/update_data_file")
async def update_data_file(req: UpdateDataFileReq):
    if not os.path.exists(req.dir_path):
        raise HTTPException(status_code=400, detail="目录不存在")

    json_path = os.path.join(req.dir_path, req.filename)
    if not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail="JSON 文件不存在")

    try:
        with open(json_path, "r", encoding="utf-8") as jf:
            data = json.load(jf)

        data["data_file"] = req.data_file

        with open(json_path, "w", encoding="utf-8") as jf:
            json.dump(data, jf, indent=2, ensure_ascii=False)

        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/rename_file")
async def rename_file(req: RenameReq):
    """实时文件重命名 API"""
    if not os.path.exists(req.dir_path):
        raise HTTPException(status_code=400, detail="目录不存在")

    old_json = req.old_filename if req.old_filename.endswith('.json') else req.old_filename + '.json'
    old_base = os.path.splitext(old_json)[0]
    old_txt = old_base + ".txt"

    old_json_path = os.path.join(req.dir_path, old_json)
    old_txt_path = os.path.join(req.dir_path, old_txt)

    if not os.path.exists(old_json_path):
        raise HTTPException(status_code=404, detail="原 JSON 文件不存在")

    new_json = req.new_filename if req.new_filename.endswith('.json') else req.new_filename + '.json'
    new_base = os.path.splitext(new_json)[0]
    new_txt = new_base + ".txt"

    new_json_path = os.path.join(req.dir_path, new_json)
    new_txt_path = os.path.join(req.dir_path, new_txt)

    if new_json == old_json:
        return {"status": "success", "new_filename": old_json}

    if os.path.exists(new_json_path):
        raise HTTPException(status_code=400, detail="目标文件名已存在")

    try:
        # 重命名 JSON 文件
        os.rename(old_json_path, new_json_path)
        # 若存在同名 TXT 备注文件，同步改名
        if os.path.exists(old_txt_path):
            os.rename(old_txt_path, new_txt_path)
        return {"status": "success", "new_filename": new_json}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/copy_file")
async def copy_file(req: FileActionReq):
    if not os.path.exists(req.dir_path):
        raise HTTPException(status_code=400, detail="目录不存在")

    src_json_path = os.path.join(req.dir_path, req.filename)
    if not os.path.exists(src_json_path):
        raise HTTPException(status_code=404, detail="源文件不存在")

    base_name = os.path.splitext(req.filename)[0]

    copy_count = 1
    new_json_name = f"{base_name}-copy.json"
    dest_json_path = os.path.join(req.dir_path, new_json_name)

    while os.path.exists(dest_json_path):
        new_json_name = f"{base_name}-copy({copy_count}).json"
        dest_json_path = os.path.join(req.dir_path, new_json_name)
        copy_count += 1

    try:
        shutil.copy2(src_json_path, dest_json_path)
        return {"status": "success", "new_filename": new_json_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/delete_file")
async def delete_file(req: FileActionReq):
    if not os.path.exists(req.dir_path):
        raise HTTPException(status_code=400, detail="目录不存在")

    json_path = os.path.join(req.dir_path, req.filename)
    base_name = os.path.splitext(req.filename)[0]
    txt_path = os.path.join(req.dir_path, base_name + ".txt")

    try:
        if os.path.exists(json_path):
            os.remove(json_path)
        if os.path.exists(txt_path):
            os.remove(txt_path)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/download_zip")
async def download_zip(dir_path: str):
    if not os.path.exists(dir_path) or not os.path.isdir(dir_path):
        raise HTTPException(status_code=400, detail="无效的目录路径")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for root, _, files in os.walk(dir_path):
            for file in files:
                if file.lower().endswith(('.json', '.txt')):
                    file_full_path = os.path.join(root, file)
                    arcname = os.path.basename(file_full_path)
                    zip_file.write(file_full_path, arcname=arcname)

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=quant_notes_export.zip"}
    )


if __name__ == "__main__":
    if not os.path.exists(DEFAULT_JSON_DIR):
        os.makedirs(DEFAULT_JSON_DIR, exist_ok=True)
        demo_data = {
            "vocab_version": "-",
            "symbol": "-",
            "formula": [ ],
            "best_score": 0,
            "formula_decoded": "-",
            "train_step": 0,
            "timeframe": "-",
            "data_file": "-",
            "mode": "-",
            "train_steps": 0
        }
        with open(os.path.join(DEFAULT_JSON_DIR, "这是一个示例.json"), "w", encoding="utf-8") as f:
            json.dump(demo_data, f, indent=2, ensure_ascii=False)

    print("==================================================")
    print("服务启动成功，请访问：http://127.0.0.1:8766")
    print("==================================================")
    uvicorn.run(app, host="127.0.0.1", port=8766)
