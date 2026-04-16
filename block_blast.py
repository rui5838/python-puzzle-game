"""
Block Blast 風パズルゲーム - 完全実装
外部アセット不使用、Pygame描画機能のみで完結
"""

import pygame
import random
import math
import sys

pygame.init()

# ============================================================
# 定数定義
# ============================================================
SCREEN_W, SCREEN_H = 450, 700
GRID_COLS, GRID_ROWS = 8, 8
CELL_SIZE = 44
GRID_OFFSET_X = (SCREEN_W - GRID_COLS * CELL_SIZE) // 2  # 左端: 29
GRID_OFFSET_Y = 80

TRAY_Y = 530          # 下部トレイのY座標基準
TRAY_CELL = 32        # トレイ内セルサイズ

FPS = 60

# カラーパレット
BG_COLOR        = (18, 20, 35)
GRID_BG         = (28, 32, 55)
GRID_LINE       = (40, 46, 75)
TEXT_COLOR      = (220, 230, 255)
HIGHLIGHT_CLR   = (255, 220, 60)
GUIDE_ALPHA     = 120
FEVER_BG1       = (40, 30, 10)
FEVER_BG2       = (60, 45, 5)

# ブロック形状定義 (shape名, cells[(row,col)], color)
SHAPES = [
    ("dot",    [(0,0)],                                         (180, 180, 180)),
    ("2x2",    [(0,0),(0,1),(1,0),(1,1)],                       (255, 100, 100)),
    ("3x3",    [(r,c) for r in range(3) for c in range(3)],     (255, 60,  60)),
    ("1x4h",   [(0,0),(0,1),(0,2),(0,3)],                       (60,  180, 255)),
    ("1x4v",   [(0,0),(1,0),(2,0),(3,0)],                       (60,  200, 255)),
    ("1x5h",   [(0,0),(0,1),(0,2),(0,3),(0,4)],                 (0,   220, 255)),
    ("1x5v",   [(0,0),(1,0),(2,0),(3,0),(4,0)],                 (0,   240, 255)),
    ("L",      [(0,0),(1,0),(2,0),(2,1)],                       (255, 160, 40)),
    ("Lrev",   [(0,1),(1,1),(2,0),(2,1)],                       (255, 200, 60)),
    ("L2",     [(0,0),(0,1),(1,0),(2,0)],                       (255, 130, 30)),
    ("L2rev",  [(0,0),(0,1),(1,1),(2,1)],                       (240, 170, 50)),
    ("Z",      [(0,0),(0,1),(1,1),(1,2)],                       (130, 255, 120)),
    ("Zrev",   [(0,1),(0,2),(1,0),(1,1)],                       (80,  220, 80)),
    ("S",      [(0,1),(0,2),(1,0),(1,1)],                       (80,  255, 180)),
    ("T",      [(0,0),(0,1),(0,2),(1,1)],                       (180, 80,  255)),
    ("U",      [(0,0),(0,2),(1,0),(1,1),(1,2)],                 (220, 80,  200)),
    ("2x1h",   [(0,0),(0,1)],                                   (100, 200, 255)),
    ("2x1v",   [(0,0),(1,0)],                                   (80,  180, 255)),
    ("3x1h",   [(0,0),(0,1),(0,2)],                             (255, 255, 100)),
    ("3x1v",   [(0,0),(1,0),(2,0)],                             (255, 240, 80)),
    ("Lsmall", [(0,0),(1,0),(1,1)],                             (255, 160, 180)),
    ("Rsmall", [(0,1),(1,0),(1,1)],                             (255, 140, 160)),
]

# フィーバー時専用形状（大型のみ）
FEVER_SHAPES = [s for s in SHAPES if s[0] in
    ("3x3","1x5h","1x5v","1x4h","1x4v","2x2","U","T","L","Lrev","L2","L2rev")]

# ============================================================
# パーティクルクラス
# ============================================================
class Particle:
    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        self.color = color
        self.vx = random.uniform(-5, 5)
        self.vy = random.uniform(-8, -1)
        self.size = random.randint(4, 10)
        self.alpha = 255
        self.decay = random.uniform(8, 18)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.35      # 重力
        self.alpha -= self.decay
        self.size = max(1, self.size - 0.2)

    def is_alive(self):
        return self.alpha > 0

    def draw(self, surface, offset_x=0, offset_y=0):
        if self.alpha <= 0:
            return
        s = pygame.Surface((int(self.size)*2, int(self.size)*2), pygame.SRCALPHA)
        a = max(0, min(255, int(self.alpha)))
        color_a = (*self.color, a)
        pygame.draw.rect(s, color_a, (0, 0, int(self.size)*2, int(self.size)*2), border_radius=2)
        surface.blit(s, (int(self.x - self.size) + offset_x, int(self.y - self.size) + offset_y))


# ============================================================
# フローティングテキストクラス
# ============================================================
class FloatingText:
    def __init__(self, text, x, y, color=(255, 230, 60), size=36):
        self.text = text
        self.x = x
        self.y = y
        self.vy = -2.0
        self.alpha = 255
        self.color = color
        self.font = pygame.font.Font(None, size)

    def update(self):
        self.y += self.vy
        self.vy *= 0.96
        self.alpha -= 4

    def is_alive(self):
        return self.alpha > 0

    def draw(self, surface, offset_x=0, offset_y=0):
        if self.alpha <= 0:
            return
        surf = self.font.render(self.text, True, self.color)
        surf.set_alpha(max(0, int(self.alpha)))
        rect = surf.get_rect(center=(int(self.x) + offset_x, int(self.y) + offset_y))
        surface.blit(surf, rect)


# ============================================================
# エフェクトマネージャ
# ============================================================
class EffectManager:
    def __init__(self):
        self.particles: list[Particle] = []
        self.texts: list[FloatingText] = []
        self.shake_frames = 0
        self.shake_intensity = 0
        self.shake_offset = (0, 0)
        self.hitstop_frames = 0

    def spawn_particles(self, cells, color, count_per_cell=12):
        """消滅するセル群からパーティクルを生成"""
        for (row, col) in cells:
            cx = GRID_OFFSET_X + col * CELL_SIZE + CELL_SIZE // 2
            cy = GRID_OFFSET_Y + row * CELL_SIZE + CELL_SIZE // 2
            for _ in range(count_per_cell):
                self.particles.append(Particle(cx, cy, color))

    def spawn_perfect_burst(self):
        """パーフェクト時：大量パーティクル"""
        colors = [(255,80,80),(80,255,120),(80,180,255),(255,220,60),(255,100,255)]
        for _ in range(300):
            x = random.randint(GRID_OFFSET_X, GRID_OFFSET_X + GRID_COLS*CELL_SIZE)
            y = random.randint(GRID_OFFSET_Y, GRID_OFFSET_Y + GRID_ROWS*CELL_SIZE)
            p = Particle(x, y, random.choice(colors))
            p.vy = random.uniform(-12, -2)
            p.vx = random.uniform(-7, 7)
            self.particles.append(p)

    def add_text(self, text, x, y, color=(255,230,60), size=36):
        self.texts.append(FloatingText(text, x, y, color, size))

    def trigger_shake(self, lines_cleared):
        """消去列数に比例した画面揺れ"""
        self.shake_frames = 8 + lines_cleared * 4
        self.shake_intensity = min(12, 3 + lines_cleared * 2)

    def trigger_perfect_shake(self):
        self.shake_frames = 30
        self.shake_intensity = 18

    def trigger_hitstop(self, ms):
        """ヒットストップ（呼び出し元でdelay）"""
        pygame.time.delay(ms)

    def update(self):
        self.particles = [p for p in self.particles if p.is_alive()]
        for p in self.particles:
            p.update()

        self.texts = [t for t in self.texts if t.is_alive()]
        for t in self.texts:
            t.update()

        if self.shake_frames > 0:
            self.shake_frames -= 1
            angle = random.uniform(0, math.pi * 2)
            self.shake_offset = (
                int(math.cos(angle) * self.shake_intensity),
                int(math.sin(angle) * self.shake_intensity)
            )
        else:
            self.shake_offset = (0, 0)

    def draw(self, surface):
        ox, oy = self.shake_offset
        for p in self.particles:
            p.draw(surface, ox, oy)
        for t in self.texts:
            t.draw(surface, ox, oy)

    @property
    def offset(self):
        return self.shake_offset


# ============================================================
# ピース（ドラッグ対象ブロック）
# ============================================================
class Piece:
    def __init__(self, shape_data):
        self.name, self.cells, self.color = shape_data
        # bounding box
        rows = [r for r,c in self.cells]
        cols = [c for r,c in self.cells]
        self.rows_span = max(rows) - min(rows) + 1
        self.cols_span = max(cols) - min(cols) + 1

    def get_grid_cells(self, grid_row, grid_col):
        """グリッド座標 (grid_row, grid_col) を基準としたセルリスト"""
        return [(grid_row + dr, grid_col + dc) for dr, dc in self.cells]


# ============================================================
# メインゲームクラス
# ============================================================
class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("Block Blast")
        self.clock = pygame.time.Clock()
        self.effect = EffectManager()

        self.font_large  = pygame.font.Font(None, 52)
        self.font_mid    = pygame.font.Font(None, 34)
        self.font_small  = pygame.font.Font(None, 24)
        self.font_tiny   = pygame.font.Font(None, 20)

        self.reset()

    def reset(self):
        # グリッド: None or color tuple
        self.grid = [[None]*GRID_COLS for _ in range(GRID_ROWS)]
        self.score = 0
        self.combo = 0
        self.total_lines = 0
        self.fever = False
        self.fever_turns = 0    # フィーバー残りターン数
        self.fever_timer = 0    # 背景アニメ用
        self.game_over = False
        self.tray = self._new_tray()
        self.dragging_idx = None    # トレイのどのピースをドラッグ中か
        self.drag_pos = (0, 0)      # マウス位置
        self.drag_ghost = None      # (grid_row, grid_col) 仮置き座標
        self.effect = EffectManager()

    def _new_tray(self):
        """新しい3ピース生成"""
        pool = FEVER_SHAPES if self.fever else SHAPES
        chosen = random.sample(pool, 3)
        return [Piece(s) for s in chosen]

    # ----------------------------------------------------------
    # グリッド操作
    # ----------------------------------------------------------
    def can_place(self, piece: Piece, gr, gc):
        """指定グリッド位置にピースを置けるか"""
        for (r, c) in piece.get_grid_cells(gr, gc):
            if r < 0 or r >= GRID_ROWS or c < 0 or c >= GRID_COLS:
                return False
            if self.grid[r][c] is not None:
                return False
        return True

    def place_piece(self, piece: Piece, gr, gc):
        """ピースをグリッドに配置"""
        for (r, c) in piece.get_grid_cells(gr, gc):
            self.grid[r][c] = piece.color

    def find_complete_lines(self):
        """揃った行・列のインデックスを返す"""
        rows = [r for r in range(GRID_ROWS) if all(self.grid[r][c] for c in range(GRID_COLS))]
        cols = [c for c in range(GRID_COLS) if all(self.grid[r][c] for r in range(GRID_ROWS))]
        return rows, cols

    def clear_lines(self, rows, cols):
        """行・列を消去してパーティクルを発生させる"""
        cleared_cells = set()
        for r in rows:
            for c in range(GRID_COLS):
                cleared_cells.add((r, c))
        for c in cols:
            for r in range(GRID_ROWS):
                cleared_cells.add((r, c))

        # パーティクル生成（消えるセルの色で）
        color_map = {}
        for (r, c) in cleared_cells:
            color = self.grid[r][c] or (200, 200, 200)
            if color not in color_map:
                color_map[color] = []
            color_map[color].append((r, c))
        for color, cells in color_map.items():
            self.effect.spawn_particles(cells, color, count_per_cell=6)

        for (r, c) in cleared_cells:
            self.grid[r][c] = None

        return len(cleared_cells)

    def is_board_empty(self):
        return all(self.grid[r][c] is None for r in range(GRID_ROWS) for c in range(GRID_COLS))

    def check_game_over(self):
        """残っているピースがどこにも置けなければゲームオーバー"""
        for piece in self.tray:
            if piece is None:
                continue
            for gr in range(GRID_ROWS):
                for gc in range(GRID_COLS):
                    if self.can_place(piece, gr, gc):
                        return False
        return True

    # ----------------------------------------------------------
    # マウス座標 → グリッドセル変換
    # ----------------------------------------------------------
    def mouse_to_grid(self, mx, my, piece: Piece):
        """
        ドラッグ中マウス位置からピースの基準(左上)グリッドセルを計算。
        マウス位置をグリッドセルに正確にスナップし、
        ピースの重心がマウスに近くなるよう補正する。
        """
        rows = [r for r, c in piece.cells]
        cols = [c for r, c in piece.cells]
        min_r = min(rows)
        min_c = min(cols)
        # ピースの重心（cells内の相対座標平均）
        center_dr = sum(rows) / len(rows) - min_r
        center_dc = sum(cols) / len(cols) - min_c

        # マウス位置をグリッド座標に変換（floatのまま）
        grid_r_f = (my - GRID_OFFSET_Y) / CELL_SIZE
        grid_c_f = (mx - GRID_OFFSET_X) / CELL_SIZE

        # 重心を引いて左上基準に変換してからint化
        gr = int(grid_r_f - center_dr)
        gc = int(grid_c_f - center_dc)
        return gr, gc

    def tray_piece_rect(self, idx):
        """トレイ内のピースのヒット判定矩形（広め）"""
        section_w = SCREEN_W // 3
        cx = section_w * idx + section_w // 2
        return pygame.Rect(cx - 65, TRAY_Y - 40, 130, 150)

    # ----------------------------------------------------------
    # スコア計算
    # ----------------------------------------------------------
    def calc_score(self, lines_count, cells_count):
        base = cells_count * 10 + lines_count * 50
        multiplier = 1 + self.combo * 0.5
        if self.fever:
            multiplier *= 2
        return int(base * multiplier)

    # ----------------------------------------------------------
    # フィーバーチェック
    # ----------------------------------------------------------
    def check_fever(self):
        if not self.fever and self.total_lines >= 10:
            self.fever = True
            self.fever_turns = 8   # 8ターン（3ピース消費=1ターン）
            self.total_lines -= 10
            self.effect.add_text("⚡ FEVER! ⚡", SCREEN_W//2, SCREEN_H//2,
                                  color=(255, 220, 60), size=56)
            self.effect.trigger_shake(5)

    # ----------------------------------------------------------
    # ドロップ処理（コアロジック）
    # ----------------------------------------------------------
    def drop_piece(self, idx, gr, gc):
        piece = self.tray[idx]
        if piece is None:
            return
        if not self.can_place(piece, gr, gc):
            return

        self.place_piece(piece, gr, gc)
        self.tray[idx] = None

        # ライン消去チェック
        rows, cols = self.find_complete_lines()
        lines = len(rows) + len(cols)

        if lines > 0:
            self.combo += 1
            self.effect.trigger_hitstop(min(80, 25 * lines))
            self.effect.trigger_shake(lines)

            cleared = self.clear_lines(rows, cols)
            gained = self.calc_score(lines, cleared)
            self.score += gained
            self.total_lines += lines

            # フローティングテキスト
            cx = GRID_OFFSET_X + GRID_COLS * CELL_SIZE // 2
            cy = GRID_OFFSET_Y + GRID_ROWS * CELL_SIZE // 2
            if lines >= 4:
                self.effect.add_text("AMAZING!!", cx, cy, (255, 100, 255), 48)
            elif lines >= 3:
                self.effect.add_text("GREAT!", cx, cy, (100, 255, 200), 44)
            elif lines >= 2:
                self.effect.add_text("NICE!", cx, cy, (255, 220, 60), 40)
            if self.combo >= 3:
                self.effect.add_text(f"COMBO x{self.combo}!", cx, cy - 50,
                                      (255, 180, 60), 36)

            # パーフェクトチェック
            if self.is_board_empty():
                self.score += 5000
                self.effect.spawn_perfect_burst()
                self.effect.trigger_perfect_shake()
                self.effect.add_text("PERFECT!!", cx, cy - 40,
                                      (255, 255, 80), 64)
                pygame.time.delay(200)
        else:
            self.combo = 0

        self.check_fever()

        # トレイが全て配置済みなら補充
        if all(p is None for p in self.tray):
            self.tray = self._new_tray()
            # フィーバーターン消費
            if self.fever:
                self.fever_turns -= 1
                if self.fever_turns <= 0:
                    self.fever = False
                    self.tray = self._new_tray()

        # ゲームオーバーチェック
        if self.check_game_over():
            self.game_over = True

    # ----------------------------------------------------------
    # イベント処理
    # ----------------------------------------------------------
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if self.game_over:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                    self.reset()
                continue

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                for i, piece in enumerate(self.tray):
                    if piece and self.tray_piece_rect(i).collidepoint(mx, my):
                        self.dragging_idx = i
                        self.drag_pos = (mx, my)
                        break

            elif event.type == pygame.MOUSEMOTION:
                if self.dragging_idx is not None:
                    self.drag_pos = event.pos
                    piece = self.tray[self.dragging_idx]
                    if piece:
                        gr, gc = self.mouse_to_grid(*event.pos, piece)
                        # ピースがグリッドに収まるようクランプ
                        rows = [r for r, c in piece.cells]
                        cols = [c for r, c in piece.cells]
                        max_dr = max(rows) - min(rows)
                        max_dc = max(cols) - min(cols)
                        gr = max(0, min(GRID_ROWS - 1 - max_dr, gr))
                        gc = max(0, min(GRID_COLS - 1 - max_dc, gc))
                        if self.can_place(piece, gr, gc):
                            self.drag_ghost = (gr, gc)
                        else:
                            self.drag_ghost = None

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if self.dragging_idx is not None:
                    piece = self.tray[self.dragging_idx]
                    if piece and self.drag_ghost:
                        self.drop_piece(self.dragging_idx, *self.drag_ghost)
                    self.dragging_idx = None
                    self.drag_ghost = None

    # ----------------------------------------------------------
    # 描画：背景
    # ----------------------------------------------------------
    def draw_background(self):
        ox, oy = self.effect.offset
        if self.fever:
            self.fever_timer += 1
            # 黄金色にゆらゆら輝く背景
            pulse = (math.sin(self.fever_timer * 0.08) + 1) / 2
            r = int(FEVER_BG1[0] + (FEVER_BG2[0] - FEVER_BG1[0]) * pulse)
            g = int(FEVER_BG1[1] + (FEVER_BG2[1] - FEVER_BG1[1]) * pulse)
            b = int(FEVER_BG1[2] + (FEVER_BG2[2] - FEVER_BG1[2]) * pulse)
            self.screen.fill((r, g, b))

            # フィーバー輝きオーバーレイ
            overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            glow_a = int(30 + 20 * math.sin(self.fever_timer * 0.15))
            pygame.draw.rect(overlay, (255, 200, 0, glow_a),
                             (0, 0, SCREEN_W, SCREEN_H))
            self.screen.blit(overlay, (ox, oy))
        else:
            self.screen.fill(BG_COLOR)

    def draw_grid(self):
        ox, oy = self.effect.offset

        # グリッド背景
        rect = pygame.Rect(GRID_OFFSET_X + ox, GRID_OFFSET_Y + oy,
                           GRID_COLS*CELL_SIZE, GRID_ROWS*CELL_SIZE)
        pygame.draw.rect(self.screen, GRID_BG, rect, border_radius=8)

        # セル線
        for r in range(GRID_ROWS+1):
            y = GRID_OFFSET_Y + r*CELL_SIZE + oy
            pygame.draw.line(self.screen, GRID_LINE,
                             (GRID_OFFSET_X+ox, y),
                             (GRID_OFFSET_X+GRID_COLS*CELL_SIZE+ox, y))
        for c in range(GRID_COLS+1):
            x = GRID_OFFSET_X + c*CELL_SIZE + ox
            pygame.draw.line(self.screen, GRID_LINE,
                             (x, GRID_OFFSET_Y+oy),
                             (x, GRID_OFFSET_Y+GRID_ROWS*CELL_SIZE+oy))

        # 消える予定ライン ハイライト（ガイドライン）
        pending_rows, pending_cols = [], []
        if self.dragging_idx is not None and self.drag_ghost:
            piece = self.tray[self.dragging_idx]
            if piece and self.can_place(piece, *self.drag_ghost):
                # 仮置き後の状態でライン判定
                tmp = [row[:] for row in self.grid]
                for (dr, dc) in piece.get_grid_cells(*self.drag_ghost):
                    tmp[dr][dc] = piece.color
                pending_rows = [r for r in range(GRID_ROWS) if all(tmp[r][c] for c in range(GRID_COLS))]
                pending_cols = [c for c in range(GRID_COLS) if all(tmp[r][c] for r in range(GRID_ROWS))]

        hl_surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        for r in pending_rows:
            rx = GRID_OFFSET_X
            ry = GRID_OFFSET_Y + r*CELL_SIZE
            pygame.draw.rect(hl_surf, (255, 230, 60, 60),
                             (rx+ox, ry+oy, GRID_COLS*CELL_SIZE, CELL_SIZE))
        for c in pending_cols:
            cx_ = GRID_OFFSET_X + c*CELL_SIZE
            cy_ = GRID_OFFSET_Y
            pygame.draw.rect(hl_surf, (255, 230, 60, 60),
                             (cx_+ox, cy_+oy, CELL_SIZE, GRID_ROWS*CELL_SIZE))
        self.screen.blit(hl_surf, (0, 0))

        # 配置済みセル描画
        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                color = self.grid[r][c]
                if color:
                    self._draw_cell(r, c, color, ox, oy)

        # ゴースト（ガイドシルエット）- グリッドにピタリとスナップした影
        if self.dragging_idx is not None and self.drag_ghost:
            piece = self.tray[self.dragging_idx]
            if piece and self.can_place(piece, *self.drag_ghost):
                ghost_surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
                for (gr, gc) in piece.get_grid_cells(*self.drag_ghost):
                    gx = GRID_OFFSET_X + gc * CELL_SIZE + ox
                    gy = GRID_OFFSET_Y + gr * CELL_SIZE + oy
                    r_c, g_c, b_c = piece.color
                    # 半透明塗りつぶし
                    pygame.draw.rect(ghost_surf, (r_c, g_c, b_c, 160),
                                     (gx + 2, gy + 2, CELL_SIZE - 4, CELL_SIZE - 4),
                                     border_radius=5)
                    # 明るい枠線でくっきり強調
                    pygame.draw.rect(ghost_surf,
                                     (min(255, r_c + 100), min(255, g_c + 100), min(255, b_c + 100), 230),
                                     (gx + 2, gy + 2, CELL_SIZE - 4, CELL_SIZE - 4),
                                     width=2, border_radius=5)
                self.screen.blit(ghost_surf, (0, 0))

    def _draw_cell(self, r, c, color, ox=0, oy=0, size=None, sx=None, sy=None):
        """単セルを美しく描画（ハイライト・影付き）"""
        cs = size or CELL_SIZE
        x = (sx if sx is not None else GRID_OFFSET_X + c*cs) + ox
        y = (sy if sy is not None else GRID_OFFSET_Y + r*cs) + oy
        pad = 2
        rect = pygame.Rect(x+pad, y+pad, cs-pad*2, cs-pad*2)

        # 影
        shadow = pygame.Surface((cs-pad*2, cs-pad*2), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0,0,0,60), (2,2,cs-pad*2-2,cs-pad*2-2), border_radius=5)
        self.screen.blit(shadow, (x+pad, y+pad))

        # 本体
        pygame.draw.rect(self.screen, color, rect, border_radius=5)

        # ハイライト（上辺に明るいライン）
        r2, g2, b2 = color
        light = (min(255,r2+80), min(255,g2+80), min(255,b2+80))
        pygame.draw.line(self.screen, light,
                         (x+pad+4, y+pad+3), (x+cs-pad-4, y+pad+3), 2)

    def draw_tray(self):
        ox, oy = self.effect.offset
        section_w = SCREEN_W // 3

        # トレイ背景
        tray_bg = pygame.Surface((SCREEN_W, 160), pygame.SRCALPHA)
        pygame.draw.rect(tray_bg, (255,255,255,12),
                         (0, 0, SCREEN_W, 160), border_radius=12)
        self.screen.blit(tray_bg, (0+ox, TRAY_Y-30+oy))

        for i, piece in enumerate(self.tray):
            if piece is None:
                continue
            # ドラッグ中は薄く
            if i == self.dragging_idx:
                continue

            cx = section_w * i + section_w // 2

            rows = [r for r, c in piece.cells]
            cols = [c for r, c in piece.cells]
            min_r, max_r = min(rows), max(rows)
            min_c, max_c = min(cols), max(cols)
            span_r = max_r - min_r + 1
            span_c = max_c - min_c + 1

            # トレイセルサイズを形状に合わせてスケール
            ts = min(TRAY_CELL, int(80 / max(span_r, span_c)))

            # 中央配置オフセット
            tx = cx - span_c * ts // 2 + ox
            ty = TRAY_Y + 30 - span_r * ts // 2 + oy

            for (dr, dc) in piece.cells:
                sx = tx + (dc - min_c) * ts
                sy = ty + (dr - min_r) * ts
                pad = 2
                rect = pygame.Rect(sx+pad, sy+pad, ts-pad*2, ts-pad*2)
                pygame.draw.rect(self.screen, piece.color, rect, border_radius=4)
                r2,g2,b2 = piece.color
                light = (min(255,r2+70),min(255,g2+70),min(255,b2+70))
                pygame.draw.line(self.screen, light,
                                 (sx+pad+3, sy+pad+2), (sx+ts-pad-3, sy+pad+2), 2)

    def draw_dragging(self):
        if self.dragging_idx is None:
            return
        piece = self.tray[self.dragging_idx]
        if piece is None:
            return
            
        mx, my = self.drag_pos
        rows = [r for r, c in piece.cells]
        cols = [c for r, c in piece.cells]
        
        # --- 変更点：配置判定と同じく、ピースの重心を計算 ---
        center_r = sum(rows) / len(rows)
        center_c = sum(cols) / len(cols)
        
        ts = CELL_SIZE
        for (dr, dc) in piece.cells:
            # --- 変更点：重心がマウス位置(mx, my)に重なるようにオフセットを計算 ---
            sx = mx + (dc - center_c) * ts - ts//2
            sy = my + (dr - center_r) * ts - ts//2
            
            pad = 2
            rect = pygame.Rect(sx+pad, sy+pad, ts-pad*2, ts-pad*2)
            
            # 半透明描画
            surf = pygame.Surface((ts-pad*2, ts-pad*2), pygame.SRCALPHA)
            r2, g2, b2 = piece.color
            pygame.draw.rect(surf, (*piece.color, 210), (0, 0, ts-pad*2, ts-pad*2), border_radius=5)
            pygame.draw.line(surf, (min(255, r2+80), min(255, g2+80), min(255, b2+80), 210),
                             (3, 2), (ts-pad*2-3, 2), 2)
            self.screen.blit(surf, (sx+pad, sy+pad))
    def draw_ui(self):
        ox, oy = self.effect.offset

        # スコア
        score_text = self.font_large.render(f"{self.score:,}", True, TEXT_COLOR)
        self.screen.blit(score_text, score_text.get_rect(centerx=SCREEN_W//2+ox, y=12+oy))

        label = self.font_tiny.render("SCORE", True, (140, 150, 180))
        self.screen.blit(label, label.get_rect(centerx=SCREEN_W//2+ox, y=8+oy))

        # コンボ表示
        if self.combo >= 2:
            ct = self.font_mid.render(f"COMBO x{self.combo}", True, (255, 200, 60))
            self.screen.blit(ct, ct.get_rect(right=SCREEN_W-10+ox, y=15+oy))

        # フィーバーインジケーター
        if self.fever:
            fx = self.font_mid.render(f"⚡FEVER! {self.fever_turns}T", True, (255, 220, 0))
            self.screen.blit(fx, fx.get_rect(x=10+ox, y=15+oy))

        # ライン累計（次フィーバーまで）
        if not self.fever:
            bar_w = 100
            bar_x = 10+ox
            bar_y = 45+oy
            prog = self.total_lines / 10
            pygame.draw.rect(self.screen, (40,46,75), (bar_x, bar_y, bar_w, 8), border_radius=4)
            pygame.draw.rect(self.screen, (80, 200, 255),
                             (bar_x, bar_y, int(bar_w*min(prog,1)), 8), border_radius=4)
            lt = self.font_tiny.render(f"FEVER {self.total_lines}/10", True, (120,140,180))
            self.screen.blit(lt, (bar_x, bar_y+10+oy))

        # セパレーター
        pygame.draw.line(self.screen, (50,58,90),
                         (0+ox, TRAY_Y-35+oy), (SCREEN_W+ox, TRAY_Y-35+oy), 1)

    def draw_game_over(self):
        # 半透明オーバーレイ
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        pygame.draw.rect(ov, (0,0,0,170), (0,0,SCREEN_W,SCREEN_H))
        self.screen.blit(ov, (0,0))

        gx = SCREEN_W//2
        gy = SCREEN_H//2 - 60
        t1 = self.font_large.render("GAME OVER", True, (255, 80, 80))
        self.screen.blit(t1, t1.get_rect(centerx=gx, y=gy))

        t2 = self.font_mid.render(f"Score: {self.score:,}", True, TEXT_COLOR)
        self.screen.blit(t2, t2.get_rect(centerx=gx, y=gy+70))

        t3 = self.font_mid.render("[R] Restart", True, (160, 200, 255))
        self.screen.blit(t3, t3.get_rect(centerx=gx, y=gy+120))

    # ----------------------------------------------------------
    # メインループ
    # ----------------------------------------------------------
    def run(self):
        while True:
            self.handle_events()
            self.effect.update()

            # --- 描画 ---
            self.draw_background()
            self.draw_grid()
            self.draw_tray()
            self.draw_dragging()
            self.draw_ui()
            self.effect.draw(self.screen)

            if self.game_over:
                self.draw_game_over()

            pygame.display.flip()
            self.clock.tick(FPS)


# ============================================================
# エントリーポイント
# ============================================================
if __name__ == "__main__":
    game = Game()
    game.run()