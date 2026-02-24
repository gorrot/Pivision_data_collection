# 数据采集模块 (PIVision)

本目录包含 PI Vision 数据采集与任务管理的全部代码与配置，便于单独维护和 git 提交。

## 目录说明

- **GUI1.py** - 任务配置界面入口（添加任务、Flask 地址、检测间隔等）
- **PIVdata2.py** - 核心逻辑：登录、刷新、空仓/磨煤机/负荷/皮带/三期监控，Flask 推送
- **empty_confirm.py** - 空仓二类标记与 `Array2Dict`
- **warn_gui.py** - 系统托盘与弹窗通知
- **robot_sendmsg.py** - 飞书推送
- **stove_turned.py** - 颜色/磨煤机 HTML 解析
- **data_collect.py** - 本地 HTML 值提取（可选）
- **config.json** - Flask 等配置（`flask.base_url` 等）

## 运行方式

在项目根目录执行（将 `data_collection` 加入路径）：

```bash
python -c "import sys; sys.path.insert(0, 'data_collection'); exec(open('data_collection/GUI1.py').read())"
```

或进入本目录后：

```bash
cd data_collection
python GUI1.py
```

## 打包 (PyInstaller)

在项目根目录执行：

1. 将 **chromedriver.exe** 放入 `data_collection/`
2. 将 **icon.png** 放入 `data_collection/images/`（若尚无图标）
3. 执行：`pyinstaller MyAppGUI.spec`

输出在 `dist/MyAppGUI/`。

## 依赖

- Python 3.x
- PyQt5, selenium, beautifulsoup4, numpy, requests, pyautogui, plyer 等（见项目根目录 requirements 或环境）
