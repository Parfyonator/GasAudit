"""UI string catalog and language-aware lookup. UK is the default language."""
from __future__ import annotations

TRANSLATIONS: dict[str, dict[str, str]] = {
    "EN": {
        "page_title": "Gas Audit Wiggle Room",
        "title": "Gas Audit — Town/Highway Wiggle Room",
        "params_header": "Period parameters",
        "upload_csv": "Upload CSV",
        "norm_unit": "Norm unit",
        "norm": "Norm (L / 100 unit)",
        "uplift": "Uplift (town +, highway -)",
        "start_fuel": "Start fuel (L)",
        "end_fuel": "End fuel (L, pinned)",
        "refuels": "Refuels (L)",
        "tol": "End-fuel tolerance (±L)",
        "clear_rows": "Clear rows",
        "csv_error": "Could not load CSV: {exc}",
        "feasible": "FEASIBLE — required total town distance {town:.1f} {unit} "
                    "within window {lo:.0f}…{hi:.0f} {unit}",
        "infeasible": "INFEASIBLE — required town {town:.1f} {unit} outside window "
                      "{lo:.0f}…{hi:.0f} {unit}",
        "no_min_highway": "No per-row highway minimums set — town share can range "
                          "0..total each day (widest window). Add minimums to constrain it.",
        "date": "Date",
        "total_dist": "Total distance ({unit})",
        "min_highway": "Min highway ({unit})",
        "save": "Save",
        "add": "Add",
        "cancel": "Cancel",
        "total_gt_zero": "Total must be greater than 0.",
        "dialog_add": "Add row",
        "dialog_edit": "Edit row",
        "split_subheader": "Per-row town / out-of-town split",
        "snap": "Snap to target",
        "lock": "🔒 Lock total",
        "lock_help": "When on, moving one day's split shifts the other days to keep the "
                     "total litres (total fuel) constant.",
        "town_fixed": "town fixed at 0 — no wiggle room",
        "row_meta": "{label} · total {total:.0f} {unit} ({km:.0f} km) · "
                    "min highway {mh:.0f} {unit}",
        "tip_delete": "Delete row",
        "tip_edit": "Edit row",
        "tip_up": "Move up",
        "tip_down": "Move down",
        "add_row": "➕ Add row",
        "bar_town": "town",
        "bar_out": "out",
        "totals_subheader": "Totals",
        "dist_mi": "Distance (mi)",
        "dist_km": "Distance (km)",
        "fuel_l": "Fuel (L)",
        "in_town": "In town",
        "out_of_town": "Out of town",
        "grand_total_fuel": "Grand total fuel",
        "implied_end_fuel": "Implied end fuel",
        "vs_pinned": "{d:+.2f} vs pinned",
        "end_ok": "✅ End fuel matches the pinned target (within tolerance).",
        "end_no": "⚠️ End fuel does not match yet — adjust the splits.",
        "export_computed": "Export computed table (CSV)",
        "export_input": "Export input CSV (re-importable)",
        "plot_required_town": "required town",
        "plot_required_town_off": "required town {town:.0f} (off-scale)",
        "plot_tol_band": "tolerance band",
        "plot_feasible_window": "feasible window",
        "plot_xlabel": "total town distance",
        "plot_ylabel": "total fuel (L)",
        "plot_title": "Total fuel vs total town distance",
    },
    "UK": {
        "page_title": "Паливний аудит — запас гнучкості",
        "title": "Паливний аудит — запас гнучкості (місто/траса)",
        "params_header": "Параметри періоду",
        "upload_csv": "Завантажити CSV",
        "norm_unit": "Одиниця норми",
        "norm": "Норма (л / 100 одиниць)",
        "uplift": "Надбавка (місто +, траса −)",
        "start_fuel": "Паливо на початок (л)",
        "end_fuel": "Паливо на кінець (л, фіксоване)",
        "refuels": "Заправки (л)",
        "tol": "Допуск палива на кінець (±л)",
        "clear_rows": "Очистити рядки",
        "csv_error": "Не вдалося завантажити CSV: {exc}",
        "feasible": "ДОПУСТИМО — потрібна загальна відстань у місті {town:.1f} {unit} "
                    "у межах вікна {lo:.0f}…{hi:.0f} {unit}",
        "infeasible": "НЕДОПУСТИМО — потрібна відстань у місті {town:.1f} {unit} "
                      "поза вікном {lo:.0f}…{hi:.0f} {unit}",
        "no_min_highway": "Не задано мінімумів траси для рядків — частка міста може бути "
                          "від 0 до загальної щодня (найширше вікно). "
                          "Додайте мінімуми, щоб обмежити.",
        "date": "Дата",
        "total_dist": "Загальна відстань ({unit})",
        "min_highway": "Мінімум траси ({unit})",
        "save": "Зберегти",
        "add": "Додати",
        "cancel": "Скасувати",
        "total_gt_zero": "Загальна відстань має бути більшою за 0.",
        "dialog_add": "Додати рядок",
        "dialog_edit": "Редагувати рядок",
        "split_subheader": "Розподіл місто / поза містом за рядками",
        "snap": "Вирівняти за ціллю",
        "lock": "🔒 Зафіксувати підсумок",
        "lock_help": "Коли увімкнено, зміна розподілу за один день зсуває інші дні, "
                     "щоб зберегти загальні літри (загальне паливо) незмінними.",
        "town_fixed": "місто зафіксовано на 0 — немає запасу гнучкості",
        "row_meta": "{label} · загалом {total:.0f} {unit} ({km:.0f} км) · "
                    "мін. траса {mh:.0f} {unit}",
        "tip_delete": "Видалити рядок",
        "tip_edit": "Редагувати рядок",
        "tip_up": "Перемістити вгору",
        "tip_down": "Перемістити вниз",
        "add_row": "➕ Додати рядок",
        "bar_town": "місто",
        "bar_out": "поза містом",
        "totals_subheader": "Підсумки",
        "dist_mi": "Відстань (миль)",
        "dist_km": "Відстань (км)",
        "fuel_l": "Паливо (л)",
        "in_town": "У місті",
        "out_of_town": "Поза містом",
        "grand_total_fuel": "Загальне паливо",
        "implied_end_fuel": "Розраховане паливо на кінець",
        "vs_pinned": "{d:+.2f} від фіксованого",
        "end_ok": "✅ Паливо на кінець відповідає фіксованій цілі (у межах допуску).",
        "end_no": "⚠️ Паливо на кінець ще не збігається — скоригуйте розподіл.",
        "export_computed": "Експорт обчисленої таблиці (CSV)",
        "export_input": "Експорт вхідного CSV (для повторного імпорту)",
        "plot_required_town": "потрібне місто",
        "plot_required_town_off": "потрібне місто {town:.0f} (поза шкалою)",
        "plot_tol_band": "смуга допуску",
        "plot_feasible_window": "допустиме вікно",
        "plot_xlabel": "загальна відстань у місті",
        "plot_ylabel": "загальне паливо (л)",
        "plot_title": "Загальне паливо — загальна відстань у місті",
    },
}


def translator(lang: str):
    """Return a t(key, **kwargs) lookup for `lang`, falling back to EN then the raw key."""
    table = TRANSLATIONS.get(lang) or TRANSLATIONS["EN"]

    def t(key: str, **kwargs) -> str:
        s = table.get(key)
        if s is None:
            s = TRANSLATIONS["EN"].get(key, key)
        return s.format(**kwargs) if kwargs else s

    return t
