"""
Olist E-Commerce Analytics Dashboard
=====================================
Proyek Akhir Analisis Data — Dicoding
Nama  : Liwa'Uddin
Email : liwauddin928@gmail.com
ID    : cdcc398d6y1474

Perbaikan dari versi sebelumnya:
1. Fix FutureWarning seaborn — palette kini pakai hue + legend=False
2. Fix sns.despine() — selalu sertakan ax eksplisit
3. Pemrosesan RFM & Delay di-cache dengan @st.cache_data
4. Error handling saat file CSV tidak ditemukan
5. Sidebar filter tanggal interaktif
6. Anotasi bar dikembalikan di semua chart
7. plt.close(fig) dipanggil setelah st.pyplot()
8. Magic number dipindahkan ke konstanta global
"""

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import seaborn as sns

# ---------------------------------------------------------------------------
# Konfigurasi Halaman
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Olist E-Commerce Dashboard",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Konstanta Global (tidak lagi hardcoded di tengah kode)
# ---------------------------------------------------------------------------
PERIOD_LABEL      = "Agustus 2017 – Juli 2018"
TOP_N_CATEGORIES  = 5
REVIEW_SCORE_MIN  = 1
REVIEW_SCORE_MAX  = 5
DELAY_XLIM        = (-5, 30)

SEGMENTS_ORDER    = ["Champions", "Loyal", "Potential", "At Risk"]
PALETTE_SEGMENT   = ["#2E8B57", "#3CB371", "#66CDAA", "#FFA07A"]
PALETTE_COMPARE   = ["#4A90E2", "#F39C12"]
PALETTE_LINE      = ["#2E8B57", "#E74C3C", "#3498DB", "#F39C12", "#9B59B6"]

DELAY_BINS        = [-100, 0, 3, 7, 15, 100]
DELAY_LABELS      = ["Tepat Waktu", "Telat 1–3 Hari", "Telat 4–7 Hari", "Telat 8–15 Hari", "Telat >15 Hari"]

# ---------------------------------------------------------------------------
# CSS Kustom
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    /* Header utama */
    .main-header {
        background: linear-gradient(135deg, #1a3a2a 0%, #2E8B57 100%);
        color: white;
        padding: 2rem 2.5rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
    }
    .main-header h1 { color: white; margin: 0; font-size: 1.8rem; }
    .main-header p  { color: rgba(255,255,255,0.8); margin: 0.4rem 0 0; font-size: 0.95rem; }

    /* Metric card kustom */
    .metric-row { display: flex; gap: 1rem; margin-bottom: 1.5rem; flex-wrap: wrap; }
    .kpi-card {
        flex: 1; min-width: 160px;
        background: white;
        border: 1px solid #e8f4ee;
        border-left: 4px solid #2E8B57;
        border-radius: 10px;
        padding: 1.1rem 1.25rem;
    }
    .kpi-label { font-size: 0.78rem; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; }
    .kpi-value { font-size: 1.6rem; font-weight: 700; color: #1a3a2a; margin-top: 0.2rem; }
    .kpi-delta { font-size: 0.78rem; color: #2E8B57; margin-top: 0.2rem; }

    /* Insight box */
    .insight-box {
        background: #f0faf5;
        border-left: 4px solid #2E8B57;
        border-radius: 0 8px 8px 0;
        padding: 0.9rem 1.1rem;
        font-size: 0.9rem;
        color: #1a3a2a;
        margin-top: 1rem;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab"] { font-weight: 600; font-size: 0.9rem; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Fungsi Utilitas Chart
# ---------------------------------------------------------------------------
def annotate_bars(ax: plt.Axes, fmt_fn=None, offset_pts: int = 5) -> None:
    """Tambahkan label nilai di atas setiap bar."""
    for patch in ax.patches:
        height = patch.get_height()
        if height == 0:
            continue
        label = fmt_fn(height) if fmt_fn else f"{height:.1f}%"
        ax.annotate(
            label,
            xy=(patch.get_x() + patch.get_width() / 2, height),
            xytext=(0, offset_pts),
            textcoords="offset points",
            ha="center", va="bottom",
            fontsize=10, fontweight="bold",
        )


def clean_axes(ax: plt.Axes) -> None:
    """Hapus border atas & kanan; pastikan ax eksplisit (fix bug global despine)."""
    sns.despine(ax=ax, left=True, bottom=False)  # FIX: selalu sertakan ax=


def apply_chart_style(fig: plt.Figure, ax: plt.Axes) -> None:
    ax.tick_params(axis="x", labelsize=10)
    ax.tick_params(axis="y", labelsize=10)
    clean_axes(ax)
    fig.tight_layout()


# ---------------------------------------------------------------------------
# Load & Cache Data
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Memuat data...")
def load_raw_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Baca CSV mentah dari disk. Raise FileNotFoundError jika tidak ada."""
    main_df  = pd.read_csv("dashboard/main_data.csv")
    delay_df = pd.read_csv("dashboard/delay_analysis.csv")

    date_cols_main  = ["order_delivered_customer_date"]
    date_cols_delay = ["order_delivered_customer_date", "order_estimated_delivery_date"]

    for col in date_cols_main:
        main_df[col] = pd.to_datetime(main_df[col], errors="coerce")
    for col in date_cols_delay:
        delay_df[col] = pd.to_datetime(delay_df[col], errors="coerce")

    # FIX: Paksa kolom nilai menjadi angka numerik (cegah error format CSV/Excel)
    if "review_score" in delay_df.columns:
        if delay_df["review_score"].dtype == object:
            delay_df["review_score"] = delay_df["review_score"].str.replace(",", ".")
        delay_df["review_score"] = pd.to_numeric(delay_df["review_score"], errors="coerce")

    if "delay_days" in delay_df.columns:
        delay_df["delay_days"] = pd.to_numeric(delay_df["delay_days"], errors="coerce")

    return main_df, delay_df


# FIX #3: Pemrosesan RFM & Delay di-cache agar tidak dihitung ulang setiap interaksi
@st.cache_data(show_spinner="Menghitung segmentasi RFM...")
def build_rfm_summary(main_df: pd.DataFrame) -> pd.DataFrame:
    recent_date = main_df["order_delivered_customer_date"].max()

    rfm = (
        main_df.groupby("customer_id")
        .agg(
            recency  =("order_delivered_customer_date", lambda x: (recent_date - x.max()).days),
            frequency=("order_id", "nunique"),
            monetary =("payment_value", "sum"),
        )
        .reset_index()
    )

    rfm = rfm[(rfm["recency"] >= 0) & (rfm["frequency"] > 0) & (rfm["monetary"] > 0)]

    def quartile_score(series: pd.Series, reverse: bool = False) -> pd.Series:
        ranked = series.rank(method="first")
        scores = pd.qcut(ranked, 4, labels=[1, 2, 3, 4]).astype(int)
        return (5 - scores) if reverse else scores

    rfm["r_score"]   = quartile_score(rfm["recency"],   reverse=True)
    rfm["f_score"]   = quartile_score(rfm["frequency"], reverse=False)
    rfm["m_score"]   = quartile_score(rfm["monetary"],  reverse=False)
    rfm["rfm_score"] = rfm["r_score"] + rfm["f_score"] + rfm["m_score"]

    def assign_segment(score: int) -> str:
        if score >= 10: return "Champions"
        if score >= 8:  return "Loyal"
        if score >= 6:  return "Potential"
        return "At Risk"

    rfm["segment"] = rfm["rfm_score"].apply(assign_segment)

    summary = rfm.groupby("segment").agg(
        customer_count=("customer_id", "count"),
        total_revenue =("monetary",    "sum"),
    )
    summary["revenue_percent"]  = summary["total_revenue"]  / summary["total_revenue"].sum()  * 100
    summary["customer_percent"] = summary["customer_count"] / summary["customer_count"].sum() * 100

    return summary.reindex(SEGMENTS_ORDER).fillna(0)


@st.cache_data(show_spinner="Menganalisis data keterlambatan...")
def build_delay_data(delay_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = delay_df.copy()
    df["delay_group"] = pd.cut(df["delay_days"], bins=DELAY_BINS, labels=DELAY_LABELS)

    top_cats    = df["product_category_name_english"].value_counts().head(TOP_N_CATEGORIES).index
    filtered    = df[df["product_category_name_english"].isin(top_cats)]
    pivot_table = pd.pivot_table(
        filtered,
        values="review_score",
        index="product_category_name_english",
        columns="delay_group",
        aggfunc="mean",
    )

    health_df = df[df["product_category_name_english"] == "health_beauty"]
    return pivot_table, health_df


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🛒 Olist Dashboard")
    st.markdown("---")

    st.markdown("**Filter Data**")
    min_date = pd.Timestamp("2017-08-01")
    max_date = pd.Timestamp("2018-07-31")

    date_range = st.date_input(
        "Rentang Tanggal",
        value=(min_date.date(), max_date.date()),
        min_value=min_date.date(),
        max_value=max_date.date(),
        help="Filter data berdasarkan tanggal pengiriman ke pelanggan",
    )

    selected_segments = st.multiselect(
        "Segmen Pelanggan",
        options=SEGMENTS_ORDER,
        default=SEGMENTS_ORDER,
        help="Pilih segmen yang ingin ditampilkan",
    )

    st.markdown("---")
    st.markdown("**Profil Analis**")
    st.markdown("Nama: Liwa'Uddin")
    st.markdown("Email: liwauddin928@gmail.com")
    st.markdown("ID: cdcc398d6y1474")
    st.markdown("---")
    st.caption("Dashboard Analisis Data — Dicoding 2026")

# ---------------------------------------------------------------------------
# Load Data dengan Error Handling
# ---------------------------------------------------------------------------
try:
    main_df, delay_df = load_raw_data()
except FileNotFoundError as e:
    st.error(
        f"**File data tidak ditemukan:** `{e.filename}`\n\n"
        "Pastikan file `main_data.csv` dan `delay_analysis.csv` "
        "berada di direktori yang sama dengan file `dashboard.py` ini."
    )
    st.stop()
except Exception as e:
    st.error(f"**Gagal memuat data:** {e}")
    st.stop()

# Filter berdasarkan tanggal dari sidebar
if len(date_range) == 2:
    start_date = pd.Timestamp(date_range[0])
    end_date   = pd.Timestamp(date_range[1])
    main_df_filtered = main_df[
        main_df["order_delivered_customer_date"].between(start_date, end_date)
    ]
    delay_df_filtered = delay_df[
        delay_df["order_delivered_customer_date"].between(start_date, end_date)
    ]
else:
    main_df_filtered  = main_df
    delay_df_filtered = delay_df

# Hitung semua ringkasan (di-cache)
rfm_summary         = build_rfm_summary(main_df_filtered)
delay_pivot, health_df = build_delay_data(delay_df_filtered)

# Filter segmen dari sidebar
rfm_filtered = rfm_summary.loc[
    [s for s in SEGMENTS_ORDER if s in selected_segments]
]

# ---------------------------------------------------------------------------
# Header Utama
# ---------------------------------------------------------------------------
st.markdown("""
<div class="main-header">
    <h1>🛒 Olist E-Commerce Analytics Dashboard</h1>
    <p>Segmentasi Pelanggan (RFM) & Evaluasi Keterlambatan Pengiriman — """ + PERIOD_LABEL + """</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Tab
# ---------------------------------------------------------------------------
tab1, tab2 = st.tabs(["👥 Segmentasi RFM", "🚚 Keterlambatan & Ulasan"])

# ===========================================================================
# TAB 1 — RFM
# ===========================================================================
with tab1:

    # KPI Cards
    total_customers = int(rfm_summary["customer_count"].sum())
    total_revenue   = rfm_summary["total_revenue"].sum()
    champ_rev       = rfm_summary.loc["Champions", "total_revenue"] if "Champions" in rfm_summary.index else 0
    champ_share     = rfm_summary.loc["Champions", "revenue_percent"] if "Champions" in rfm_summary.index else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Pelanggan",          f"{total_customers:,}")
    col2.metric("Total Pendapatan",          f"R$ {total_revenue/1e6:.2f}M")
    col3.metric("Pendapatan Champions",      f"R$ {champ_rev/1e6:.2f}M")
    col4.metric("Kontribusi Champions",      f"{champ_share:.1f}%")

    st.markdown("---")

    col_left, col_right = st.columns(2)

    # --- Chart 1: Total Pendapatan ---
    with col_left:
        st.subheader("Total Pendapatan per Segmen")

        fig1, ax1 = plt.subplots(figsize=(7, 4.5))
        sns.set_theme(style="whitegrid", font_scale=1.0)

        # FIX #1: Tambahkan hue + legend=False agar tidak muncul FutureWarning
        sns.barplot(
            x=rfm_filtered.index,
            y="total_revenue",
            hue=rfm_filtered.index,
            data=rfm_filtered.reset_index(),
            palette=PALETTE_SEGMENT[: len(rfm_filtered)],
            legend=False,
            ax=ax1,
        )

        ax1.set_xlabel("Segmen Pelanggan", fontsize=11, fontweight="bold", labelpad=10)
        ax1.set_ylabel("Total Pendapatan (R$)", fontsize=11, fontweight="bold", labelpad=10)
        ax1.set_title("")
        ax1.yaxis.set_major_formatter(
            ticker.FuncFormatter(lambda x, _: f"R$ {x * 1e-6:.1f}M")
        )

        annotate_bars(ax1, fmt_fn=lambda v: f"R$ {v/1_000:,.0f}K")
        apply_chart_style(fig1, ax1)

        st.pyplot(fig1)
        plt.close(fig1)  # FIX #7: Bebaskan memori

    # --- Chart 2: % Populasi vs % Pendapatan ---
    with col_right:
        st.subheader("% Populasi vs % Kontribusi Pendapatan")

        METRIC_MAP = {
            "customer_percent": "% Populasi Pelanggan",
            "revenue_percent":  "% Kontribusi Pendapatan",
        }
        plot_data = (
            rfm_filtered[list(METRIC_MAP.keys())]
            .reset_index()
            .melt(id_vars="segment", var_name="Metric", value_name="Percentage")
        )
        plot_data["Metric"] = plot_data["Metric"].map(METRIC_MAP)

        fig2, ax2 = plt.subplots(figsize=(7, 4.5))
        sns.barplot(
            x="segment",
            y="Percentage",
            hue="Metric",
            data=plot_data,
            palette=PALETTE_COMPARE,
            ax=ax2,
        )

        ax2.set_xlabel("Segmen Pelanggan", fontsize=11, fontweight="bold", labelpad=10)
        ax2.set_ylabel("Persentase (%)", fontsize=11, fontweight="bold", labelpad=10)
        ax2.set_title("")
        ax2.set_ylim(0, 60)
        ax2.legend(title=None, loc="upper right", fontsize=10)

        annotate_bars(ax2)
        apply_chart_style(fig2, ax2)

        st.pyplot(fig2)
        plt.close(fig2)  # FIX #7

    # Tabel Ringkasan
    st.markdown("---")
    st.subheader("Tabel Ringkasan Segmen")

    display_df = rfm_filtered.copy()
    display_df["total_revenue"]    = display_df["total_revenue"].apply(lambda v: f"R$ {v:,.0f}")
    display_df["customer_percent"] = display_df["customer_percent"].apply(lambda v: f"{v:.1f}%")
    display_df["revenue_percent"]  = display_df["revenue_percent"].apply(lambda v: f"{v:.1f}%")
    display_df = display_df.rename(columns={
        "customer_count":   "Jumlah Pelanggan",
        "total_revenue":    "Total Pendapatan",
        "customer_percent": "% Populasi",
        "revenue_percent":  "% Pendapatan",
    })
    st.dataframe(display_df, use_container_width=True)

    st.markdown("""
    <div class="insight-box">
    💡 <strong>Insight:</strong> Segmen <em>Champions</em> hanya mencakup sekitar 18% populasi pelanggan
    namun menyumbang hampir 48% total pendapatan — menunjukkan bahwa program retensi dan reward
    untuk segmen ini akan memberikan ROI tertinggi.
    </div>
    """, unsafe_allow_html=True)


# ===========================================================================
# TAB 2 — DELAY & REVIEWS
# ===========================================================================
with tab2:
    st.subheader("Dampak Keterlambatan Pengiriman terhadap Kepuasan Pelanggan")

    col_a, col_b = st.columns(2)

    # --- Chart 3: Regresi Health & Beauty ---
    with col_a:
        st.markdown("**Tren Skor: Kategori Health & Beauty**")

        fig3, ax3 = plt.subplots(figsize=(6.5, 4.5))
        sns.regplot(
            x="delay_days",
            y="review_score",
            data=health_df,
            scatter_kws={"alpha": 0.25, "color": "#3498DB", "s": 20},
            line_kws={"color": "#E74C3C", "linewidth": 2},
            ax=ax3,
        )

        ax3.set_xlabel("Keterlambatan (hari)", fontsize=11, fontweight="bold", labelpad=10)
        ax3.set_ylabel("Skor Ulasan (1–5)",    fontsize=11, fontweight="bold", labelpad=10)
        ax3.set_xlim(DELAY_XLIM)
        ax3.set_ylim(REVIEW_SCORE_MIN - 0.2, REVIEW_SCORE_MAX + 0.2)

        clean_axes(ax3)  # FIX #2: ax eksplisit
        fig3.tight_layout()

        st.pyplot(fig3)
        plt.close(fig3)

    # --- Chart 4: Line Toleransi Keterlambatan ---
    with col_b:
        st.markdown(f"**Toleransi Keterlambatan: {TOP_N_CATEGORIES} Kategori Teratas**")

        # FIX: Cegah error "no numeric data" jika data kosong karena filter tanggal
        if delay_pivot.empty:
            st.warning("⚠️ Data kosong pada rentang tanggal ini. Silakan atur ulang tanggal.")
        else:
            fig4, ax4 = plt.subplots(figsize=(7, 4.5))
            
            # Pastikan jumlah warna sesuai dengan jumlah kategori
            warna_sesuai = PALETTE_LINE[:len(delay_pivot)]
            delay_pivot.T.plot(marker="o", ax=ax4, color=warna_sesuai, linewidth=2, markersize=5)

            ax4.set_xlabel("Kelompok Keterlambatan", fontsize=11, fontweight="bold", labelpad=10)
            ax4.set_ylabel("Rata-rata Skor Ulasan",  fontsize=11, fontweight="bold", labelpad=10)
            ax4.set_ylim(REVIEW_SCORE_MIN, REVIEW_SCORE_MAX)
            ax4.tick_params(axis="x", rotation=15)
            ax4.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=9, title="Kategori")

            clean_axes(ax4) 
            fig4.tight_layout()
            st.pyplot(fig4)
            plt.close(fig4)
    # --- Heatmap Pivot ---
    st.markdown("---")
    st.subheader("Heatmap: Rata-rata Skor Ulasan per Kategori & Keterlambatan")

    fig5, ax5 = plt.subplots(figsize=(12, 4))
    sns.heatmap(
        delay_pivot,
        annot=True,
        fmt=".2f",
        cmap="RdYlGn",
        vmin=REVIEW_SCORE_MIN,
        vmax=REVIEW_SCORE_MAX,
        linewidths=0.4,
        ax=ax5,
        cbar_kws={"label": "Rata-rata Skor"},
    )
    ax5.set_xlabel("Kelompok Keterlambatan", fontsize=11, fontweight="bold", labelpad=10)
    ax5.set_ylabel("Kategori Produk",        fontsize=11, fontweight="bold", labelpad=10)
    ax5.tick_params(axis="x", rotation=20)
    ax5.tick_params(axis="y", rotation=0)
    fig5.tight_layout()

    st.pyplot(fig5)
    plt.close(fig5)

    st.markdown("""
    <div class="insight-box">
    💡 <strong>Insight:</strong> Batas toleransi maksimal pelanggan terhadap keterlambatan adalah
    <strong>3 hari</strong>. Setelah melewati ambang ini, rata-rata skor ulasan di seluruh kategori
    turun secara drastis — bahkan pada kategori yang sebelumnya memiliki skor tertinggi sekalipun.
    Prioritaskan SLA pengiriman ≤ 3 hari untuk mempertahankan kepuasan pelanggan.
    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("---")
st.caption("© Liwa'Uddin 2026 — Dicoding Data Analysis Project · Data: Olist E-Commerce")
