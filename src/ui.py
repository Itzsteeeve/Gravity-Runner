from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional, Tuple

import pygame

from .config import (
    BG_DARK,
    LOGICAL_HEIGHT,
    LOGICAL_WIDTH,
    NEON_ACCENT,
    NEON_BLUE,
    NEON_PINK,
    TEXT_MAIN,
)

_BG_STATIC_CACHE: dict[tuple[int, int], tuple[pygame.Surface, pygame.Surface]] = {}


@dataclass
class NeonFonts:
    big: pygame.font.Font
    medium: pygame.font.Font
    small: pygame.font.Font


def create_fonts() -> NeonFonts:
    # Use a readable system font; the neon outline/glow is what sells the look.
    big = pygame.font.SysFont("DejaVu Sans Mono", 54, bold=True)
    medium = pygame.font.SysFont("DejaVu Sans Mono", 28, bold=True)
    small = pygame.font.SysFont("DejaVu Sans Mono", 20, bold=True)
    return NeonFonts(big=big, medium=medium, small=small)


def draw_neon_text(
    surf: pygame.Surface,
    text: str,
    pos: Tuple[int, int],
    font: pygame.font.Font,
    main_color: Tuple[int, int, int],
    outline_color: Tuple[int, int, int],
    center: bool = False,
) -> None:
    x, y = pos
    text_surf = font.render(text, True, main_color)
    glow_surf = font.render(text, True, outline_color)
    rect = text_surf.get_rect()
    if center:
        rect.center = (x, y)
    else:
        rect.topleft = (x, y)

    # Soft glow via multiple blits.
    for dx, dy, a in [(-2, 0, 1), (2, 0, 1), (0, -2, 1), (0, 2, 1), (-1, -1, 1), (1, 1, 1)]:
        tmp = glow_surf.copy()
        tmp.set_alpha(170)
        surf.blit(tmp, rect.move(dx, dy))

    surf.blit(text_surf, rect)


def fit_text(font: pygame.font.Font, text: str, max_width: int) -> str:
    if font.size(text)[0] <= max_width:
        return text
    suffix = "..."
    for n in range(len(text), 0, -1):
        candidate = text[:n].rstrip() + suffix
        if font.size(candidate)[0] <= max_width:
            return candidate
    return suffix


def draw_background(surf: pygame.Surface, time_s: float) -> None:
    surf.fill(BG_DARK)
    w, h = surf.get_size()
    cache_key = (w, h)
    cached = _BG_STATIC_CACHE.get(cache_key)
    if cached is None:
        grid = pygame.Surface((w, h), pygame.SRCALPHA)
        # Layer 1: slow parallax grid.
        step_far = 52
        for x in range(-step_far, w + step_far, step_far):
            pygame.draw.line(grid, (14, 34, 54, 130), (x, 0), (x, h), 1)
        for y in range(-step_far, h + step_far, step_far):
            pygame.draw.line(grid, (14, 34, 54, 130), (0, y), (w, y), 1)

        # Layer 2: denser near grid.
        step_near = 34
        for x in range(-step_near, w + step_near, step_near):
            pygame.draw.line(grid, (24, 62, 96, 90), (x, 0), (x, h), 1)
        for y in range(-step_near, h + step_near, step_near):
            pygame.draw.line(grid, (24, 62, 96, 90), (0, y), (w, y), 1)

        vig = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(18):
            alpha = int(8 + i * 2.7)
            pygame.draw.rect(vig, (0, 0, 0, alpha), pygame.Rect(i * 9, i * 6, w - i * 18, h - i * 12), width=5)
        _BG_STATIC_CACHE[cache_key] = (grid, vig)
        cached = (grid, vig)
    grid, vig = cached
    surf.blit(grid, (0, 0))

    # Animated neon light bands.
    bands = pygame.Surface((w, h), pygame.SRCALPHA)
    for i in range(5):
        y = int((h * (0.15 + i * 0.16)) + 22 * math.sin(time_s * 1.1 + i * 0.8))
        pygame.draw.line(bands, (*NEON_BLUE, 26), (0, y), (w, y + 14), 3)
        pygame.draw.line(bands, (*NEON_PINK, 18), (0, y + 8), (w, y - 6), 2)
    surf.blit(bands, (0, 0))
    surf.blit(vig, (0, 0))


class MenuSection(Enum):
    MAIN = auto()
    DIFFICULTY = auto()
    SETTINGS = auto()
    SKINS = auto()


@dataclass(frozen=True)
class MenuSettingsView:
    sound_enabled: bool
    sfx_volume: float  # 0..1
    fx_intensity: float  # 0..1+


@dataclass(frozen=True)
class MenuSkinItemView:
    id: str
    name: str
    description: str
    price_credits: int
    owned: bool
    equipped: bool
    preview_player_down: Tuple[int, int, int]
    preview_player_up: Tuple[int, int, int]
    preview_accent: Tuple[int, int, int]
    preview_gate_wall: Tuple[int, int, int]
    preview_gate_outline: Tuple[int, int, int]
    preview_spike: Tuple[int, int, int]


@dataclass(frozen=True)
class MenuView:
    section: MenuSection
    prev_section: Optional[MenuSection]
    transition_progress: float  # 0..1

    # Cursor animation (only used for current section)
    cursor_y: float

    # Per-section selection indices
    main_selected: int
    difficulty_selected: int
    settings_selected: int
    skins_selected: int
    skins_scroll: int
    skins_visible_rows: int

    # Data
    difficulty_mode_label: str
    credits: int
    score: int
    highscore: int
    skin_items: List[MenuSkinItemView]
    settings: MenuSettingsView

    # Optional feedback
    message: Optional[str]


def _draw_panel_background(surf: pygame.Surface, alpha: int) -> None:
    panel = pygame.Surface((LOGICAL_WIDTH, LOGICAL_HEIGHT), pygame.SRCALPHA)
    # Slightly off-center panel for a premium feel.
    x = LOGICAL_WIDTH // 2 - 270
    y = 285
    w = 540
    h = 310
    pygame.draw.rect(panel, (0, 0, 0, alpha), pygame.Rect(x, y, w, h), border_radius=18)
    pygame.draw.rect(panel, (*NEON_ACCENT, min(200, alpha + 20)), pygame.Rect(x, y, w, h), width=2, border_radius=18)
    surf.blit(panel, (0, 0))


def _draw_row(
    surf: pygame.Surface,
    fonts: NeonFonts,
    text: str,
    pos: Tuple[int, int],
    is_selected: bool,
    highlight_color: Tuple[int, int, int],
    outline_color: Tuple[int, int, int],
) -> None:
    x, y = pos
    # Cursor pulse.
    t = pygame.time.get_ticks() / 1000.0
    pulse = 0.5 + 0.5 * math.sin(t * 6.0 + x * 0.01)

    if is_selected:
        # Neon behind highlight.
        bg = pygame.Surface((LOGICAL_WIDTH, LOGICAL_HEIGHT), pygame.SRCALPHA)
        rect = pygame.Rect(LOGICAL_WIDTH // 2 - 250, y - 14, 500, 44)
        pygame.draw.rect(bg, (*highlight_color, int(55 + 40 * pulse)), rect, border_radius=14)
        pygame.draw.rect(bg, (*outline_color, int(170 + 40 * pulse)), rect, width=2, border_radius=14)
        surf.blit(bg, (0, 0))

    # Slightly different font sizes based on selection for extra “alive” feel.
    f = fonts.medium if is_selected else fonts.small
    main_col = highlight_color if is_selected else TEXT_MAIN
    glow_col = outline_color if is_selected else NEON_PINK
    draw_neon_text(
        surf,
        text,
        (x, y),
        f,
        main_color=main_col,
        outline_color=glow_col,
        center=False,
    )


def _draw_cursor_arrow(surf: pygame.Surface, x: int, center_y: int) -> None:
    # Stable marker aligned to selected row center.
    t = pygame.time.get_ticks() / 1000.0
    bob = int(2 * math.sin(t * 7.0))
    cy = center_y + bob
    outer = [(x, cy), (x - 14, cy - 11), (x - 14, cy + 11)]
    inner = [(x - 2, cy), (x - 11, cy - 7), (x - 11, cy + 7)]
    pygame.draw.polygon(surf, NEON_BLUE, outer)
    pygame.draw.polygon(surf, NEON_ACCENT, inner)


def _draw_menu_section(
    surf: pygame.Surface,
    fonts: NeonFonts,
    view: MenuView,
    section: MenuSection,
    highlight_y: float,
    alpha: int = 255,
) -> None:
    # Render menu section onto surf (assumed to already be a transparent temp surface when alpha < 255).
    # Title
    title_y = 155
    draw_neon_text(
        surf,
        "GRAVITY RUNNER",
        (LOGICAL_WIDTH // 2, title_y),
        fonts.big,
        main_color=TEXT_MAIN,
        outline_color=NEON_ACCENT,
        center=True,
    )
    draw_neon_text(
        surf,
        "One action. Flip gravity. Survive.",
        (LOGICAL_WIDTH // 2, title_y + 90),
        fonts.medium,
        main_color=NEON_BLUE,
        outline_color=NEON_PINK,
        center=True,
    )

    # Panel container (alpha via temp surface).
    _draw_panel_background(surf, alpha=38)

    # Cursor arrow for sections except shop (shop uses list arrow).
    if section != MenuSection.SKINS:
        _draw_cursor_arrow(surf, LOGICAL_WIDTH // 2 - 235, int(highlight_y + 10))

    # Content positions.
    row_x = LOGICAL_WIDTH // 2 - 120
    row_y0 = 360
    row_h = 48

    # Global economy info.
    draw_neon_text(
        surf,
        f"CREDITS {view.credits}",
        (LOGICAL_WIDTH // 2 - 250, 300),
        fonts.small,
        main_color=NEON_ACCENT,
        outline_color=NEON_BLUE,
        center=False,
    )
    draw_neon_text(
        surf,
        f"BEST {view.highscore}",
        (LOGICAL_WIDTH // 2 + 120, 300),
        fonts.small,
        main_color=TEXT_MAIN,
        outline_color=NEON_PINK,
        center=False,
    )

    if section == MenuSection.MAIN:
        items = ["START", "DIFFICULTY", "SETTINGS", "SKINS", "EXIT"]
        descs = [
            "Start a run (ENTER)",
            f"Current: {view.difficulty_mode_label}",
            "Sound + FX (ENTER to toggle/cycle)",
            f"Buy & equip skins (credits: {view.credits})",
            "Quit (ENTER)",
        ]
        selected = view.main_selected
        desc = descs[selected] if 0 <= selected < len(descs) else ""

        for i, it in enumerate(items):
            is_sel = i == selected
            _draw_row(
                surf,
                fonts,
                it,
                (row_x, row_y0 + i * row_h),
                is_selected=is_sel,
                highlight_color=NEON_BLUE if is_sel else (120, 160, 220),
                outline_color=NEON_ACCENT,
            )

        draw_neon_text(
            surf,
            desc,
            (LOGICAL_WIDTH // 2, row_y0 + len(items) * row_h + 14),
            fonts.small,
            main_color=TEXT_MAIN,
            outline_color=NEON_PINK,
            center=True,
        )

        draw_neon_text(
            surf,
            "In-game: UP / W x2 / Left Click",
            (LOGICAL_WIDTH // 2, row_y0 + len(items) * row_h + 40),
            fonts.small,
            main_color=NEON_ACCENT,
            outline_color=NEON_BLUE,
            center=True,
        )
        draw_neon_text(
            surf,
            f"Last score {view.score}",
            (LOGICAL_WIDTH // 2, row_y0 + len(items) * row_h + 66),
            fonts.small,
            main_color=TEXT_MAIN,
            outline_color=NEON_PINK,
            center=True,
        )

    elif section == MenuSection.DIFFICULTY:
        items = ["EASY", "NORMAL", "HARD", "BACK"]
        selected = view.difficulty_selected
        for i, it in enumerate(items):
            is_sel = i == selected
            _draw_row(
                surf,
                fonts,
                it,
                (row_x, row_y0 + i * row_h),
                is_selected=is_sel,
                highlight_color=NEON_ACCENT if is_sel else (150, 220, 210),
                outline_color=NEON_BLUE,
            )

        draw_neon_text(
            surf,
            "Affects obstacle tempo & gap tightness.",
            (LOGICAL_WIDTH // 2, row_y0 + len(items) * row_h + 14),
            fonts.small,
            main_color=TEXT_MAIN,
            outline_color=NEON_ACCENT,
            center=True,
        )
        draw_neon_text(
            surf,
            "Score multiplier: EASY x1 | NORMAL x2 | HARD x3",
            (LOGICAL_WIDTH // 2, row_y0 + len(items) * row_h + 40),
            fonts.small,
            main_color=NEON_BLUE,
            outline_color=NEON_PINK,
            center=True,
        )

    elif section == MenuSection.SETTINGS:
        # Derived row labels from state.
        rows: List[str] = [
            f"SOUND: {'ON' if view.settings.sound_enabled else 'OFF'}",
            f"SFX VOL: {int(view.settings.sfx_volume * 100)}%",
            f"FX INT: {int(view.settings.fx_intensity * 100)}%",
            "BACK",
        ]
        selected = view.settings_selected
        for i, it in enumerate(rows):
            is_sel = i == selected
            _draw_row(
                surf,
                fonts,
                it,
                (row_x, row_y0 + i * row_h),
                is_selected=is_sel,
                highlight_color=NEON_PINK if is_sel else (200, 140, 190),
                outline_color=NEON_ACCENT,
            )

        draw_neon_text(
            surf,
            "ENTER toggles/cycles. UP/DOWN moves selection.",
            (LOGICAL_WIDTH // 2, row_y0 + len(rows) * row_h + 14),
            fonts.small,
            main_color=TEXT_MAIN,
            outline_color=NEON_BLUE,
            center=True,
        )

    elif section == MenuSection.SKINS:
        # Reworked shop: left list + right large preview panel (fits full screen).
        items = list(view.skin_items)
        selected = view.skins_selected
        list_x = LOGICAL_WIDTH // 2 - 340
        list_y0 = 360
        list_w = 290
        list_h = 44
        list_gap = 8
        visible_rows = max(3, view.skins_visible_rows)
        total_rows = len(items) + 1
        max_scroll = max(0, total_rows - visible_rows)
        scroll = max(0, min(view.skins_scroll, max_scroll))

        # Draw list entries (+BACK) only in visible viewport.
        for vis_i in range(visible_rows):
            i = scroll + vis_i
            if i >= total_rows:
                break
            y = list_y0 + vis_i * (list_h + list_gap)
            is_sel = i == selected
            if i == len(items):
                label = "BACK"
                status = ""
                col = NEON_BLUE
                out = NEON_ACCENT
            else:
                skin_item = items[i]
                label = skin_item.name
                if skin_item.equipped:
                    status = "EQUIPPED"
                    col = NEON_ACCENT
                    out = NEON_BLUE
                elif skin_item.owned:
                    status = "OWNED"
                    col = NEON_BLUE
                    out = NEON_ACCENT
                else:
                    status = f"{skin_item.price_credits:,} CR"
                    col = (210, 180, 255)
                    out = NEON_PINK

            row = pygame.Surface((LOGICAL_WIDTH, LOGICAL_HEIGHT), pygame.SRCALPHA)
            fill_a = 66 if is_sel else 30
            pygame.draw.rect(row, (8, 18, 30, fill_a), pygame.Rect(list_x, y, list_w, list_h), border_radius=10)
            pygame.draw.rect(row, (*out, 220 if is_sel else 120), pygame.Rect(list_x, y, list_w, list_h), width=2, border_radius=10)
            surf.blit(row, (0, 0))

            if is_sel:
                draw_neon_text(surf, ">", (list_x - 18, y + 10), fonts.small, main_color=NEON_ACCENT, outline_color=NEON_BLUE, center=False)

            label_draw = fit_text(fonts.small, label, 150)
            draw_neon_text(surf, label_draw, (list_x + 14, y + 10), fonts.small, main_color=col, outline_color=out, center=False)
            if status:
                status_draw = fit_text(fonts.small, status, 120)
                draw_neon_text(surf, status_draw, (list_x + list_w - 130, y + 10), fonts.small, main_color=col, outline_color=out, center=False)

        # Scroll hint.
        if max_scroll > 0:
            draw_neon_text(
                surf,
                f"Scroll {scroll + 1}/{max_scroll + 1}",
                (list_x, list_y0 - 26),
                fonts.small,
                main_color=NEON_BLUE,
                outline_color=NEON_ACCENT,
                center=False,
            )

        # Right preview panel
        panel_x = LOGICAL_WIDTH // 2 - 25
        panel_y = 350
        panel_w = 360
        panel_h = 236
        p = pygame.Surface((LOGICAL_WIDTH, LOGICAL_HEIGHT), pygame.SRCALPHA)
        pygame.draw.rect(p, (8, 18, 30, 52), pygame.Rect(panel_x, panel_y, panel_w, panel_h), border_radius=14)
        pygame.draw.rect(p, (*NEON_ACCENT, 170), pygame.Rect(panel_x, panel_y, panel_w, panel_h), width=2, border_radius=14)
        surf.blit(p, (0, 0))

        if 0 <= selected < len(items):
            it = items[selected]
            draw_neon_text(surf, it.name, (panel_x + 18, panel_y + 14), fonts.medium, main_color=NEON_ACCENT, outline_color=NEON_BLUE, center=False)
            desc_draw = fit_text(fonts.small, it.description, panel_w - 32)
            draw_neon_text(surf, desc_draw, (panel_x + 18, panel_y + 52), fonts.small, main_color=TEXT_MAIN, outline_color=NEON_PINK, center=False)

            # Proper round ball preview with glow.
            cx, cy = panel_x + 105, panel_y + 145
            glow = pygame.Surface((LOGICAL_WIDTH, LOGICAL_HEIGHT), pygame.SRCALPHA)
            for rr, aa in [(38, 42), (30, 68), (24, 96)]:
                pygame.draw.circle(glow, (*it.preview_player_down, aa), (cx, cy), rr)
            surf.blit(glow, (0, 0))
            pygame.draw.circle(surf, it.preview_player_down, (cx, cy), 18)
            pygame.draw.circle(surf, it.preview_accent, (cx, cy), 12, width=3)

            # Obstacle preview on right side.
            gate = pygame.Rect(panel_x + 220, panel_y + 98, 56, 110)
            pygame.draw.rect(surf, it.preview_gate_wall, gate, border_radius=8)
            pygame.draw.rect(surf, it.preview_gate_outline, gate.inflate(-6, -6), width=2, border_radius=6)
            pygame.draw.polygon(surf, it.preview_spike, [(gate.left + 8, gate.top + 8), (gate.left + 26, gate.top + 8), (gate.left + 17, gate.top - 10)])
            pygame.draw.polygon(surf, it.preview_spike, [(gate.right - 26, gate.bottom - 8), (gate.right - 8, gate.bottom - 8), (gate.right - 17, gate.bottom + 10)])

            state_text = "EQUIPPED" if it.equipped else ("OWNED" if it.owned else f"PRICE {it.price_credits:,} CR")
            draw_neon_text(surf, state_text, (panel_x + 18, panel_y + 196), fonts.small, main_color=NEON_BLUE, outline_color=NEON_ACCENT, center=False)
        else:
            draw_neon_text(surf, "Return to main menu", (panel_x + 18, panel_y + 96), fonts.medium, main_color=TEXT_MAIN, outline_color=NEON_BLUE, center=False)

        draw_neon_text(
            surf,
            f"Wallet {view.credits:,} CR   |   Last score {view.score}",
            (LOGICAL_WIDTH // 2, 592),
            fonts.small,
            main_color=NEON_ACCENT,
            outline_color=NEON_BLUE,
            center=True,
        )

    # Optional feedback toast.
    if view.message:
        draw_neon_text(
            surf,
            view.message,
            (LOGICAL_WIDTH // 2, LOGICAL_HEIGHT - 40),
            fonts.small,
            main_color=(255, 140, 210),
            outline_color=NEON_BLUE,
            center=True,
        )


def draw_menu(surf: pygame.Surface, fonts: NeonFonts, view: MenuView) -> None:
    # Menu is rendered on top of the already animated background.
    row_y0 = 360
    row_h = 48

    def selected_y_for(section: MenuSection) -> float:
        if section == MenuSection.MAIN:
            return row_y0 + view.main_selected * row_h
        if section == MenuSection.DIFFICULTY:
            return row_y0 + view.difficulty_selected * row_h
        if section == MenuSection.SETTINGS:
            return row_y0 + view.settings_selected * row_h
        # SKINS
        vis_i = max(0, view.skins_selected - max(0, view.skins_scroll))
        return row_y0 + vis_i * (44 + 8)

    # Transition (slide + fade)
    if view.prev_section is not None and view.transition_progress > 0.0 and view.transition_progress < 1.0:
        p = max(0.0, min(1.0, view.transition_progress))

        prev_tmp = pygame.Surface((LOGICAL_WIDTH, LOGICAL_HEIGHT), pygame.SRCALPHA)
        prev_y_offset = int((-60.0) * p)
        _draw_menu_section(
            prev_tmp,
            fonts,
            view=view,
            section=view.prev_section,
            highlight_y=selected_y_for(view.prev_section),
        )
        prev_tmp.set_alpha(int(255 * (1.0 - p)))

        cur_tmp = pygame.Surface((LOGICAL_WIDTH, LOGICAL_HEIGHT), pygame.SRCALPHA)
        cur_y_offset = int(60.0 * (1.0 - p))
        _draw_menu_section(
            cur_tmp,
            fonts,
            view=view,
            section=view.section,
            highlight_y=view.cursor_y,
        )
        cur_tmp.set_alpha(int(255 * p))

        surf.blit(prev_tmp, (0, prev_y_offset))
        surf.blit(cur_tmp, (0, cur_y_offset))
        return

    # No transition: render just the current section.
    tmp = pygame.Surface((LOGICAL_WIDTH, LOGICAL_HEIGHT), pygame.SRCALPHA)
    _draw_menu_section(tmp, fonts, view=view, section=view.section, highlight_y=view.cursor_y)
    surf.blit(tmp, (0, 0))


def draw_pause_menu(surf: pygame.Surface, fonts: NeonFonts, selected_index: int, cursor_y: float) -> None:
    # Dim gameplay behind pause panel.
    dim = pygame.Surface((LOGICAL_WIDTH, LOGICAL_HEIGHT), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 130))
    surf.blit(dim, (0, 0))

    draw_neon_text(
        surf,
        "PAUSED",
        (LOGICAL_WIDTH // 2, 190),
        fonts.big,
        main_color=TEXT_MAIN,
        outline_color=NEON_ACCENT,
        center=True,
    )
    draw_neon_text(
        surf,
        "ESC to resume",
        (LOGICAL_WIDTH // 2, 242),
        fonts.small,
        main_color=NEON_BLUE,
        outline_color=NEON_PINK,
        center=True,
    )

    _draw_panel_background(surf, alpha=48)
    _draw_cursor_arrow(surf, LOGICAL_WIDTH // 2 - 235, int(cursor_y + 10))

    row_x = LOGICAL_WIDTH // 2 - 120
    row_y0 = 360
    row_h = 48
    items = ["RESUME", "MAIN MENU"]
    for i, it in enumerate(items):
        is_sel = i == selected_index
        _draw_row(
            surf,
            fonts,
            it,
            (row_x, row_y0 + i * row_h),
            is_selected=is_sel,
            highlight_color=NEON_BLUE if is_sel else (120, 160, 220),
            outline_color=NEON_ACCENT,
        )


def draw_hud(
    surf: pygame.Surface,
    fonts: NeonFonts,
    score: int,
    highscore: int,
    phase_name: str,
    gravity_down: bool,
    difficulty_label: str,
    score_multiplier: int,
    credits: int,
    active_event_label: str | None = None,
    active_event_remaining_s: float = 0.0,
) -> None:
    draw_neon_text(
        surf,
        f"SCORE {score}",
        (24, 18),
        fonts.small,
        main_color=TEXT_MAIN,
        outline_color=NEON_ACCENT,
        center=False,
    )
    draw_neon_text(
        surf,
        f"BEST {highscore}",
        (24, 46),
        fonts.small,
        main_color=NEON_BLUE,
        outline_color=NEON_PINK,
        center=False,
    )

    # Gravity indicator
    arrow = "DOWN" if gravity_down else "UP"
    draw_neon_text(
        surf,
        arrow,
        (24, LOGICAL_HEIGHT - 44),
        fonts.small,
        main_color=NEON_ACCENT,
        outline_color=NEON_BLUE,
        center=False,
    )

    draw_neon_text(
        surf,
        f"DIFF {difficulty_label}  x{score_multiplier}",
        (24, 74),
        fonts.small,
        main_color=NEON_PINK,
        outline_color=NEON_ACCENT,
        center=False,
    )
    draw_neon_text(
        surf,
        f"CREDITS {credits}",
        (LOGICAL_WIDTH - 210, 46),
        fonts.small,
        main_color=NEON_ACCENT,
        outline_color=NEON_BLUE,
        center=False,
    )

    if active_event_label:
        draw_neon_text(
            surf,
            f"EVENT {active_event_label} {active_event_remaining_s:0.1f}s",
            (LOGICAL_WIDTH - 350, 74),
            fonts.small,
            main_color=(255, 226, 140),
            outline_color=NEON_PINK,
            center=False,
        )


def draw_game_over(
    surf: pygame.Surface,
    fonts: NeonFonts,
    score: int,
    highscore: int,
    remaining_s: float,
) -> None:
    draw_neon_text(
        surf,
        "GAME OVER",
        (LOGICAL_WIDTH // 2, 200),
        fonts.big,
        main_color=NEON_PINK,
        outline_color=NEON_ACCENT,
        center=True,
    )
    draw_neon_text(
        surf,
        f"Score: {score}",
        (LOGICAL_WIDTH // 2, 290),
        fonts.medium,
        main_color=TEXT_MAIN,
        outline_color=NEON_BLUE,
        center=True,
    )
    draw_neon_text(
        surf,
        f"Best: {highscore}",
        (LOGICAL_WIDTH // 2, 332),
        fonts.small,
        main_color=NEON_BLUE,
        outline_color=NEON_ACCENT,
        center=True,
    )
    draw_neon_text(
        surf,
        f"Restarting in {remaining_s:.1f}s",
        (LOGICAL_WIDTH // 2, 420),
        fonts.small,
        main_color=TEXT_MAIN,
        outline_color=NEON_PINK,
        center=True,
    )

