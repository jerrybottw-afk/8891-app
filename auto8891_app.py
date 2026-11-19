import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import pandas as pd
import re
import csv
from datetime import datetime

# ==================== 全域狀態變數 ====================
df_global = None
current_filtered_df = None
current_valuation_data = None


# ==================== 資料庫與清洗核心函式 ====================
def load_data():
    try:
        conn = sqlite3.connect("auto8891.db")
        df = pd.read_sql("SELECT * FROM car", conn)
        conn.close()

        expected_cols = ["縣市", "標題", "年份", "里程", "價格", "圖片連結", "車輛連結"]
        for col in expected_cols:
            if col not in df.columns:
                df[col] = ""

        if "連結" in df.columns and "車輛連結" not in df.columns:
            df["車輛連結"] = df["連結"]
        elif "車輛連結" in df.columns and "連結" not in df.columns:
            df["連結"] = df["車輛連結"]

        df["價格_數值"] = df["價格"].apply(to_number)
        df["里程_數值"] = df["里程"].apply(to_number)
        return df
    except Exception as e:
        messagebox.showerror(
            "錯誤", f"讀取資料庫失敗: {e}\n請確認同目錄下是否有 auto8891.db"
        )
        return pd.DataFrame(
            columns=["縣市", "標題", "年份", "里程", "價格", "圖片連結", "車輛連結"]
        )


def to_number(s):
    if not isinstance(s, str):
        return 0
    digits = re.sub(r"[^0-9.]", "", s)
    if not digits:
        return 0
    num = float(digits)
    return int(num * 10000) if "萬" in s else int(num)


# ==================== UI 事件處理函式 ====================
def populate_table(target_df, tree_widget):
    for item in tree_widget.get_children():
        tree_widget.delete(item)

    if target_df is not None and not target_df.empty:
        for _, row in target_df.iterrows():
            tree_widget.insert(
                "",
                "end",
                values=(
                    row["縣市"],
                    row["標題"],
                    row["年份"],
                    row["里程"],
                    row["價格"],
                ),
            )


def filter_cars():
    global current_filtered_df
    keyword = search_entry.get().strip()
    selected_county = county_combo.get().strip()

    filtered_df = df_global.copy()
    if selected_county and selected_county != "全部縣市":
        filtered_df = filtered_df[filtered_df["縣市"] == selected_county]
    if keyword:
        filtered_df = filtered_df[
            filtered_df["標題"].astype(str).str.contains(keyword, case=False, na=False)
        ]

    current_filtered_df = filtered_df
    populate_table(filtered_df, tree)
    status_var.set(f"🔍 篩選完成：共找到 {len(filtered_df)} 筆符合的車源。")


def reset_filter():
    global current_filtered_df
    search_entry.delete(0, tk.END)
    county_combo.current(0)
    current_filtered_df = df_global.copy()
    populate_table(df_global, tree)
    status_var.set(f"✨ 已顯示全部車源，總計 {len(df_global)} 筆。")


def export_query_csv():
    target_df = current_filtered_df if current_filtered_df is not None else df_global
    if target_df is None or target_df.empty:
        messagebox.showwarning("提示", "目前沒有車源資料可供匯出！")
        return

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    keyword = search_entry.get().strip()
    county = county_combo.get().strip()

    file_suffix = []
    if county and county != "全部縣市":
        file_suffix.append(county)
    if keyword:
        file_suffix.append(keyword)
    suffix_str = ("_" + "_".join(file_suffix)) if file_suffix else ""
    default_name = f"8891車源清單{suffix_str}_{timestamp_str}.csv"

    file_path = filedialog.asksaveasfilename(
        title="匯出車源清單為 CSV",
        defaultextension=".csv",
        initialfile=default_name,
        filetypes=[("CSV 檔案 (*.csv)", "*.csv"), ("所有檔案 (*.*)", "*.*")],
    )
    if not file_path:
        return

    try:
        cols_to_export = ["縣市", "標題", "年份", "里程", "價格", "車輛連結"]
        available_cols = [c for c in cols_to_export if c in target_df.columns]
        target_df[available_cols].to_csv(file_path, index=False, encoding="utf-8-sig")
        messagebox.showinfo(
            "匯出成功",
            f"車源清單已成功匯出至：\n{file_path}\n共匯出 {len(target_df)} 筆資料。",
        )
    except Exception as e:
        messagebox.showerror("匯出失敗", f"寫入 CSV 檔案失敗:\n{e}")


def calculate_valuation():
    global current_valuation_data
    keyword = val_keyword_entry.get().strip()
    year_str = val_year_entry.get().strip()
    km_str = val_km_entry.get().strip()

    if df_global is None or df_global.empty:
        messagebox.showwarning("警告", "資料庫中沒有車輛資料，無法估價！")
        return

    if not keyword:
        messagebox.showwarning("提示", "請輸入欲估價的車款關鍵字！")
        return

    matched = df_global[
        df_global["標題"].astype(str).str.contains(keyword, case=False, na=False)
    ]
    if year_str.isdigit():
        year_matched = matched[
            matched["年份"].astype(str).str.contains(str(year_str), na=False)
        ]
        if not year_matched.empty:
            matched = year_matched

    matched = matched[matched["價格_數值"] > 0]

    if matched.empty:
        current_valuation_data = None
        val_result_var.set(
            f"⚠️ 找不到與「{keyword} ({year_str}年)」相符的有效車源，無法提供精準估價。"
        )
        return

    avg_price = matched["價格_數值"].mean()
    min_price = matched["價格_數值"].min()
    max_price = matched["價格_數值"].max()
    count = len(matched)

    km_tip = ""
    avg_db_km = 0
    diff_km = 0
    if km_str.isdigit():
        target_km = float(km_str)
        avg_db_km = matched["里程_數值"].mean()
        if avg_db_km > 0:
            diff_km = target_km - avg_db_km
            km_tip = f"\n• 里程修正提示：輸入里程比市場均值 ({avg_db_km:,.0f} km) {'多' if diff_km > 0 else '少'}約 {abs(diff_km):,.0f} km。"

    bargain_5 = avg_price * 0.95
    bargain_10 = avg_price * 0.90

    current_valuation_data = {
        "keyword": keyword,
        "year": year_str,
        "km": km_str,
        "count": count,
        "avg_price": avg_price,
        "min_price": min_price,
        "max_price": max_price,
        "km_tip": km_tip.strip() if km_tip else "",
        "avg_db_km": avg_db_km,
        "diff_km": diff_km,
        "bargain_5": bargain_5,
        "bargain_10": bargain_10,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "matched_df": matched.copy(),
    }

    result_text = (
        f"📊 【{keyword} - {year_str}年 智慧估價報告】\n"
        f"--------------------------------------------------\n"
        f"• 參考樣本數：{count} 輛相似車源\n"
        f"• 市場平均行情價：約 【NT$ {avg_price:,.0f} 元】 ({avg_price/10000:.1f} 萬)\n"
        f"• 合理開價區間：NT$ {min_price:,.0f} ~ {max_price:,.0f} 元{km_tip}\n"
        f"💡 建議買賣議價空間可落在平均行情的 -5% ~ -10% 區間 (約 NT$ {bargain_10:,.0f} ~ {bargain_5:,.0f} 元)。\n\n"
        f"💾 提示：可點擊上方「儲存估價報告 (CSV)」按鈕將本次估價數據及 {count} 筆樣本明細匯出保存。"
    )
    val_result_var.set(result_text)


def save_valuation_csv():
    if current_valuation_data is None:
        messagebox.showwarning(
            "提示",
            "目前尚未產出估價結果！\n請先輸入條件並點擊「🚀 開始智慧估價與市場行情分析」後再儲存。",
        )
        return

    val = current_valuation_data
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    year_label = val["year"] if val["year"] else "不限年份"
    default_name = f"估價報告_{val['keyword']}_{year_label}_{timestamp_str}.csv"

    file_path = filedialog.asksaveasfilename(
        title="儲存估價報告為 CSV",
        defaultextension=".csv",
        initialfile=default_name,
        filetypes=[("CSV 檔案 (*.csv)", "*.csv"), ("所有檔案 (*.*)", "*.*")],
    )
    if not file_path:
        return

    try:
        with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            # 區塊一：估價指標摘要
            writer.writerow(["=== 8891 中古車 AI 智慧估價報告 ===", ""])
            writer.writerow(["評估車款關鍵字", val["keyword"]])
            writer.writerow(
                ["出廠年份", f"{val['year']} 年" if val["year"] else "不限年份"]
            )
            writer.writerow(
                ["預計行駛里程", f"{val['km']} km" if val["km"] else "未指定"]
            )
            writer.writerow(["參考樣本數", f"{val['count']} 輛"])
            writer.writerow(
                [
                    "市場平均行情價",
                    f"NT$ {val['avg_price']:,.0f} 元 ({val['avg_price']/10000:.1f} 萬)",
                ]
            )
            writer.writerow(
                [
                    "合理開價區間",
                    f"NT$ {val['min_price']:,.0f} ~ {val['max_price']:,.0f} 元",
                ]
            )
            writer.writerow(
                [
                    "建議議價空間 (-5% ~ -10%)",
                    f"NT$ {val['bargain_10']:,.0f} ~ {val['bargain_5']:,.0f} 元",
                ]
            )
            if val.get("km_tip"):
                writer.writerow(["里程修正提示", val["km_tip"].replace("\n", " ")])
            writer.writerow(["報告產出時間", val["timestamp"]])
            writer.writerow([])

            # 區塊二：參考樣本明細清單
            writer.writerow(
                [f"=== 參考車源樣本明細 (共 {val['count']} 筆) ===", "", "", "", "", ""]
            )
            cols = ["縣市", "標題", "年份", "里程", "價格", "車輛連結"]
            valid_cols = [c for c in cols if c in val["matched_df"].columns]
            writer.writerow(valid_cols)
            for _, row in val["matched_df"][valid_cols].iterrows():
                writer.writerow(row.tolist())

        messagebox.showinfo(
            "儲存成功",
            f"估價報告已成功儲存至：\n{file_path}\n共收錄 {val['count']} 筆參考車源明細！",
        )
    except Exception as e:
        messagebox.showerror("儲存失敗", f"寫入 CSV 檔案失敗:\n{e}")


def reload_database():
    global df_global, all_counties, current_filtered_df
    df_global = load_data()
    current_filtered_df = df_global.copy()
    all_counties = ["全部縣市"] + sorted(list(df_global["縣市"].dropna().unique()))
    county_combo["values"] = all_counties
    county_combo.current(0)
    populate_table(df_global, tree)
    messagebox.showinfo(
        "成功", f"已成功從 SQLite 重新載入最新車源！共 {len(df_global)} 筆。"
    )


# ==================== 主程式介面建構 ====================
root = tk.Tk()
root.title("中古車快速查詢與智慧估價系統")
root.geometry("1100x720")
root.minsize(1000, 650)

df_global = load_data()
current_filtered_df = df_global.copy()
all_counties = (
    ["全部縣市"] + sorted(list(df_global["縣市"].dropna().unique()))
    if not df_global.empty
    else ["全部縣市"]
)

# 樣式設定
style = ttk.Style()
style.theme_use("clam")

BG_COLOR = "#F8FAFC"
PRIMARY_COLOR = "#0284C7"
SUCCESS_COLOR = "#16A34A"
TEXT_COLOR = "#1E293B"

root.configure(bg=BG_COLOR)

style.configure(".", font=("Microsoft JhengHei", 10))
style.configure("TLabel", background=BG_COLOR, foreground=TEXT_COLOR)
style.configure(
    "Header.TLabel", font=("Microsoft JhengHei", 16, "bold"), foreground="#0F172A"
)
style.configure(
    "TNotebook.Tab", font=("Microsoft JhengHei", 11, "bold"), padding=[15, 8]
)

# 🛠️ 關鍵：設定按鈕樣式並加入 .map() 確保 Hover 時顏色不被吃掉
style.configure(
    "Primary.TButton",
    font=("Microsoft JhengHei", 10, "bold"),
    foreground="white",
    background=PRIMARY_COLOR,
)
style.map(
    "Primary.TButton",
    background=[("active", "#0284C7"), ("pressed", "#0369A1")],
    foreground=[("active", "white"), ("pressed", "white")],
)

style.configure(
    "Success.TButton",
    font=("Microsoft JhengHei", 10, "bold"),
    foreground="white",
    background=SUCCESS_COLOR,
)
style.map(
    "Success.TButton",
    background=[("active", "#15803D"), ("pressed", "#166534")],
    foreground=[("active", "white"), ("pressed", "white")],
)

header_frame = ttk.Frame(root, padding=15)
header_frame.pack(fill="x")

ttk.Label(
    header_frame, text="🚗 8891 中古車行情與智慧估價系統", style="Header.TLabel"
).pack(side="left")
reload_btn = ttk.Button(header_frame, text="🔄 重新載入資料庫", command=reload_database)
reload_btn.pack(side="right")

notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True, padx=15, pady=5)

tab_query = ttk.Frame(notebook)
tab_valuation = ttk.Frame(notebook)

notebook.add(tab_query, text=" 🔍 車源快速查詢 ")
notebook.add(tab_valuation, text=" 💰 AI 智慧估價系統 ")

# 分頁一
query_frame = ttk.Frame(tab_query, padding=15)
query_frame.pack(fill="both", expand=True)

filter_box = ttk.LabelFrame(query_frame, text=" 多維度條件篩選 ", padding=10)
filter_box.pack(fill="x", pady=(0, 10))

ttk.Label(filter_box, text="縣市：").pack(side="left", padx=(5, 2))
county_combo = ttk.Combobox(filter_box, values=all_counties, width=12, state="readonly")
county_combo.pack(side="left", padx=5)
county_combo.current(0)

ttk.Label(filter_box, text="關鍵字：").pack(side="left", padx=(15, 2))
search_entry = ttk.Entry(filter_box, width=22, font=("Microsoft JhengHei", 10))
search_entry.pack(side="left", padx=5)

search_btn = ttk.Button(
    filter_box, text="查詢", command=filter_cars, style="Primary.TButton"
)
search_btn.pack(side="left", padx=5)

reset_btn = ttk.Button(filter_box, text="顯示全部", command=reset_filter)
reset_btn.pack(side="left", padx=5)

export_query_btn = ttk.Button(
    filter_box,
    text="💾 匯出車源 (CSV)",
    command=export_query_csv,
    style="Success.TButton",
)
export_query_btn.pack(side="left", padx=5)

table_frame = ttk.Frame(query_frame)
table_frame.pack(fill="both", expand=True)

columns = ("縣市", "標題", "年份", "里程", "價格")
tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=16)

tree.heading("縣市", text="所在縣市")
tree.heading("標題", text="車款完整名稱")
tree.heading("年份", text="出廠年份")
tree.heading("里程", text="行駛里程")
tree.heading("價格", text="售價")

tree.column("縣市", width=90, anchor="center")
tree.column("標題", width=400, anchor="w")
tree.column("年份", width=80, anchor="center")
tree.column("里程", width=110, anchor="center")
tree.column("價格", width=100, anchor="center")

scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
tree.configure(yscrollcommand=scrollbar.set)

tree.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

status_var = tk.StringVar(value=f"✨ 系統就緒，目前載入 {len(df_global)} 筆車源資料。")
status_bar = ttk.Label(
    query_frame,
    textvariable=status_var,
    font=("Microsoft JhengHei", 9),
    foreground="#64748B",
)
status_bar.pack(anchor="w", pady=(5, 0))

populate_table(df_global, tree)

# 分頁二
val_container = ttk.Frame(tab_valuation, padding=20)
val_container.pack(fill="both", expand=True)

val_frame = ttk.LabelFrame(val_container, text=" 輸入欲估價車輛的條件細節 ", padding=20)
val_frame.pack(fill="x", padx=10, pady=10)
val_frame.columnconfigure(1, weight=1)

ttk.Label(
    val_frame,
    text="車款關鍵字 (如 RAV4 / Altis / C300)：",
    font=("Microsoft JhengHei", 10, "bold"),
).grid(row=0, column=0, sticky="w", pady=8)
val_keyword_entry = ttk.Entry(val_frame, width=30, font=("Microsoft JhengHei", 11))
val_keyword_entry.grid(row=0, column=1, sticky="w", pady=8)
val_keyword_entry.insert(0, "Altis")

ttk.Label(
    val_frame, text="出廠年份 (如 2019)：", font=("Microsoft JhengHei", 10, "bold")
).grid(row=1, column=0, sticky="w", pady=8)
val_year_entry = ttk.Entry(val_frame, width=30, font=("Microsoft JhengHei", 11))
val_year_entry.grid(row=1, column=1, sticky="w", pady=8)
val_year_entry.insert(0, "2019")

ttk.Label(
    val_frame, text="預計行駛里程 (km，選填)：", font=("Microsoft JhengHei", 10, "bold")
).grid(row=2, column=0, sticky="w", pady=8)
val_km_entry = ttk.Entry(val_frame, width=30, font=("Microsoft JhengHei", 11))
val_km_entry.grid(row=2, column=1, sticky="w", pady=8)
val_km_entry.insert(0, "65000")

val_btn_box = ttk.Frame(val_frame)
val_btn_box.grid(row=3, column=0, columnspan=2, pady=15)

calc_btn = ttk.Button(
    val_btn_box,
    text="🚀 開始智慧估價與市場行情分析",
    command=calculate_valuation,
    style="Primary.TButton",
)
calc_btn.pack(side="left", padx=8)

save_val_btn = ttk.Button(
    val_btn_box,
    text="💾 儲存估價報告 (CSV)",
    command=save_valuation_csv,
    style="Success.TButton",
)
save_val_btn.pack(side="left", padx=8)

val_result_var = tk.StringVar(
    value="請於上方輸入車款、年份與里程後，點擊按鈕產出行情分析報告。"
)
result_box = ttk.LabelFrame(val_container, text=" 市場行情評估結果 ", padding=15)
result_box.pack(fill="both", expand=True, padx=10, pady=10)

result_label = ttk.Label(
    result_box,
    textvariable=val_result_var,
    font=("Microsoft JhengHei", 11),
    foreground="#0369A1",
    justify="left",
)
result_label.pack(anchor="nw", fill="both", expand=True)

if __name__ == "__main__":
    root.mainloop()
