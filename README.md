# 美股新闻联动看板 · 部署说明

一共4个文件，缺一不可：
- `index.html` — 网页本体，读取 `data.json` 来显示
- `data.json` — 数据文件（现在里面是示例数据，方便你先预览效果）
- `fetch_data.py` — 抓数据的脚本，之后会自动生成真正的 `data.json`
- `.github/workflows/update-data.yml` — 定时任务配置

## 第一步：注册 Finnhub（免费）

1. 打开 https://finnhub.io/register 注册一个账号（不需要信用卡）
2. 登录后在 Dashboard 首页能看到一串 API Key，先复制保存好

## 第二步：建一个 GitHub 仓库

1. 去 https://github.com 注册/登录账号
2. 右上角 "+" → "New repository"，名字随便取（比如 `stock-dashboard`），选 **Public**（Pages 免费版需要公开仓库），点 Create

3. 上传前3个"普通"文件（`index.html`、`data.json`、`fetch_data.py`、`README.md`）：
   - 进入刚建好的仓库页面，点绿色 "Add file" 按钮 → 选 "Upload files"
   - 把这4个文件从你电脑拖进网页中间的方框（或点方框里的链接选择文件）
   - 拖完后往下滑，点绿色 "Commit changes" 完成上传

4. 上传 `update-data.yml`（这个比较特殊，因为它要放在 `.github/workflows/` 这个子文件夹里，直接拖拽上传不会自动建文件夹，要用下面这个方法）：
   - 还是在仓库页面，点 "Add file" → 这次选 **"Create new file"**（不是 Upload files）
   - 在最上面的文件名输入框里，直接打字输入：`.github/workflows/update-data.yml`
     （打斜杠 `/` 的时候 GitHub 会自动帮你建好对应的文件夹，不用另外去建）
   - 打开我给你的 `update-data.yml` 文件，把里面的内容全选复制，粘贴到下面的大文本框里
   - 滑到底部，点绿色 "Commit changes" 完成

   完成后，仓库首页应该能看到 `index.html`、`data.json`、`fetch_data.py`、`README.md` 这4个文件，
   以及一个 `.github` 文件夹（点进去能看到 `workflows/update-data.yml`）。

## 第三步：把 Finnhub 的 Key 加进仓库的"密钥"里（不会公开）

1. 仓库页面 → Settings → 左侧 Secrets and variables → Actions
2. 点 "New repository secret"
3. Name 填：`FINNHUB_API_KEY`
4. Value 填：你刚才复制的 Finnhub key
5. 保存

## 第四步：打开 GitHub Pages（让网页能被访问）

1. 仓库页面 → Settings → 左侧 Pages
2. Source 选 "Deploy from a branch"，Branch 选 `main`，文件夹选 `/ (root)`，保存
3. 等一两分钟，页面上会出现一个网址，形如：
   `https://你的用户名.github.io/仓库名/`
   这就是你以后随时随地能打开看的网址

## 第五步：先手动跑一次，生成真实数据

1. 仓库页面 → 顶部 Actions 标签
2. 左侧点 "Update Stock Data"
3. 右边点 "Run workflow" → 再点绿色的 "Run workflow" 确认
4. 等大概1分钟，跑完后仓库里的 `data.json` 会被自动更新成真实数据
5. 打开第四步拿到的网址，刷新一下，就能看到真实行情了

之后每个交易日（周一到周五）会在协调世界时 13:00（大约对应美股开盘前）自动跑一次，
不需要你做任何事。如果哪天想立刻刷新，就重复第五步手动点一次 "Run workflow"。

## 常见问题

**打开网页显示"还没有读取到数据"？**
说明 `data.json` 还是初始状态或抓取失败，去 Actions 页面看看最近一次运行有没有报错（点进去能看到详细日志）。

**某支股票一直显示"数据获取失败"？**
免费额度对分时K线、财报日历这些接口有限制，属于正常情况，不影响其他股票正常显示。

**想换股票？**
打开 `fetch_data.py`，改最上面 `SYMBOLS = [...]` 这一行，换成你想看的股票代码即可。

**新闻旁边的"该时段涨跌"是AI分析的原因吗？**
不是。这是纯数据（新闻发布时间 + 那个时间点前后的价格变化 + 成交量倍数），
没有用AI去解读"为什么"，因果判断需要你自己看新闻内容。
如果想要AI自动写"涨跌原因"的文字（类似最早演示版那种），
需要在 `fetch_data.py` 里再加一段调用 Claude API 的代码，把新闻标题喂给模型生成解读——
这个可以作为下一步升级，告诉我你想做我再帮你加。
