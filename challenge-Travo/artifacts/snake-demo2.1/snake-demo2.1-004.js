<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Snake Demo</title>
  <style>
    :root {
      color-scheme: dark;
    }

    body {
      margin: 0;
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
      background: #0f1220;
      color: #e8ecff;
      display: grid;
      min-height: 100vh;
      place-items: center;
    }

    .wrap {
      width: min(92vw, 760px);
      display: grid;
      gap: 12px;
    }

    .hud {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 10px 12px;
      background: #141a33;
      border: 1px solid #27305a;
      border-radius: 10px;
    }

    .hud-left {
      display: flex;
      align-items: baseline;
      gap: 14px;
      flex-wrap: wrap;
    }

    .label {
      opacity: 0.8;
      font-size: 12px;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }

    .value {
      font-variant-numeric: tabular-nums;
      font-size: 16px;
      font-weight: 700;
    }

    .status {
      opacity: 0.9;
      font-size: 13px;
    }

    button {
      appearance: none;
      border: 1px solid #34407a;
      background: #1c2450;
      color: #e8ecff;
      padding: 9px 12px;
      border-radius: 10px;
      cursor: pointer;
      font-weight: 700;
    }

    button:hover {
      background: #222c60;
    }

    button:active {
      transform: translateY(1px);
    }

    canvas {
      width: 100%;
      height: auto;
      background: #0b0f1f;
      border: 1px solid #27305a;
      border-radius: 12px;
      display: block;
    }

    .hint {
      opacity: 0.7;
      font-size: 12px;
      text-align: center;
      margin-bottom: 4px;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hud">
      <div class="hud-left">
        <div>
          <div class="label">Puntaje</div>
          <div class="value" id="scoreValue">0</div>
        </div>
        <div>
          <div class="label">Estado</div>
          <div class="status" id="statusText">Listo</div>
        </div>
      </div>
      <button id="resetBtn" type="button">Reiniciar</button>
    </div>

    <canvas id="game" width="640" height="480" aria-label="Snake game"></canvas>
    <div class="hint">Controles: Flechas / WASD. Reiniciar: botón o R.</div>
  </div>

  <script>
    'use strict';

    const CANVAS_BG = '#0b0f1f';
    const GRID_COLOR = '#12183a';
    const SNAKE_HEAD_COLOR = '#8ee6ff';
    const SNAKE_BODY_COLOR = '#4fb3ff';
    const FOOD_COLOR = '#ff5f7a';
    const OVERLAY_COLOR = 'rgba(0, 0, 0, 0.55)';
    const OVERLAY_TEXT_COLOR = '#ffffff';

    const CELL_SIZE = 20;
    const TICK_MS = 110;
    const INITIAL_LENGTH = 3;

    const DIR = Object.freeze({
      up: { x: 0, y: -1, key: 'up' },
      down: { x: 0, y: 1, key: 'down' },
      left: { x: -1, y: 0, key: 'left' },
      right: { x: 1, y: 0, key: 'right' }
    });

    const OPPOSITE_DIR_KEY = Object.freeze({
      up: 'down',
      down: 'up',
      left: 'right',
      right: 'left'
    });

    const canvas = document.getElementById('game');
    const ctx = canvas.getContext('2d', { alpha: false });

    const scoreValueEl = document.getElementById('scoreValue');
    const statusTextEl = document.getElementById('statusText');
    const resetBtn = document.getElementById('resetBtn');

    const gridCols = Math.floor(canvas.width / CELL_SIZE);
    const gridRows = Math.floor(canvas.height / CELL_SIZE);

    const state = {
      score: 0,
      snake: [],
      dir: DIR.right,
      nextDir: DIR.right,
      food: { x: 0, y: 0 },
      gameOver: false,
      running: false,
      lastTickAt: 0,
      rafId: 0,
      needsRender: true
    };

    function clampToGridCell(pos) {
      return {
        x: Math.max(0, Math.min(gridCols - 1, pos.x)),
        y: Math.max(0, Math.min(gridRows - 1, pos.y))
      };
    }

    function cellKey(x, y) {
      return `${x},${y}`;
    }

    function updateHud() {
      scoreValueEl.textContent = String(state.score);
      statusTextEl.textContent = state.gameOver ? 'Game Over' : (state.running ? 'Jugando' : 'Listo');
    }

    function setDirection(dirKey) {
      if (!DIR[dirKey]) return;
      if (state.gameOver) return;

      const currentKey = state.dir.key;
      if (OPPOSITE_DIR_KEY[currentKey] === dirKey) return;

      state.nextDir = DIR[dirKey];
    }

    function spawnFood() {
      const occupied = new Set(state.snake.map(s => cellKey(s.x, s.y)));
      const freeCells = [];

      for (let y = 0; y < gridRows; y++) {
        for (let x = 0; x < gridCols; x++) {
          const key = cellKey(x, y);
          if (!occupied.has(key)) freeCells.push({ x, y });
        }
      }

      if (freeCells.length === 0) {
        state.food = { x: -1, y: -1 };
        return;
      }

      const idx = Math.floor(Math.random() * freeCells.length);
      state.food = freeCells[idx];
    }

    function resetGame() {
      state.score = 0;
      state.gameOver = false;
      state.running = true;
      state.lastTickAt = 0;
      state.needsRender = true;

      const center = clampToGridCell({
        x: Math.floor(gridCols / 2),
        y: Math.floor(gridRows / 2)
      });

      state.dir = DIR.right;
      state.nextDir = DIR.right;

      const snake = [];
      for (let i = INITIAL_LENGTH - 1; i >= 0; i--) {
        snake.push({ x: center.x - i, y: center.y });
      }
      state.snake = snake;

      spawnFood();
      updateHud();
      render();

      if (state.rafId) cancelAnimationFrame(state.rafId);
      state.rafId = requestAnimationFrame(loop);
    }

    function endGame() {
      state.gameOver = true;
      state.running = false;
      updateHud();
      state.needsRender = true;
      render();
    }

    function step() {
      if (!state.running || state.gameOver) return;

      state.dir = state.nextDir;

      const head = state.snake[0];
      const next = { x: head.x + state.dir.x, y: head.y + state.dir.y };

      if (next.x < 0 || next.x >= gridCols || next.y < 0 || next.y >= gridRows) {
        endGame();
        return;
      }

      const ateFood = next.x === state.food.x && next.y === state.food.y;

      const bodyToCheck = ateFood ? state.snake : state.snake.slice(0, -1);
      const bodyKeys = new Set(bodyToCheck.map(s => cellKey(s.x, s.y)));
      if (bodyKeys.has(cellKey(next.x, next.y))) {
        endGame();
        return;
      }

      state.snake.unshift(next);

      if (ateFood) {
        state.score += 1;
        spawnFood();
        updateHud();
      } else {
        state.snake.pop();
      }

      state.needsRender = true;
    }

    function drawGrid() {
      ctx.fillStyle = CANVAS_BG;
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      ctx.strokeStyle = GRID_COLOR;
      ctx.lineWidth = 1;

      for (let x = 0; x <= gridCols; x++) {
        const px = x * CELL_SIZE + 0.5;
        ctx.beginPath();
        ctx.moveTo(px, 0);
        ctx.lineTo(px, gridRows * CELL_SIZE);
        ctx.stroke();
      }

      for (let y = 0; y <= gridRows; y++) {
        const py = y * CELL_SIZE + 0.5;
        ctx.beginPath();
        ctx.moveTo(0, py);
        ctx.lineTo(gridCols * CELL_SIZE, py);
        ctx.stroke();
      }
    }

    function fillCell(x, y, color) {
      ctx.fillStyle = color;
      ctx.fillRect(x * CELL_SIZE + 1, y * CELL_SIZE + 1, CELL_SIZE - 2, CELL_SIZE - 2);
    }

    function render() {
      drawGrid();

      if (state.food.x >= 0 && state.food.y >= 0) {
        fillCell(state.food.x, state.food.y, FOOD_COLOR);
      }

      for (let i = state.snake.length - 1; i >= 0; i--) {
        const seg = state.snake[i];
        fillCell(seg.x, seg.y, i === 0 ? SNAKE_HEAD_COLOR : SNAKE_BODY_COLOR);
      }

      if (state.gameOver) {
        ctx.fillStyle = OVERLAY_COLOR;
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        ctx.fillStyle = OVERLAY_TEXT_COLOR;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        ctx.font = '700 40px system-ui, -apple-system, Segoe UI, Roboto, Arial';
        ctx.fillText('Game Over', canvas.width / 2, canvas.height / 2 - 20);

        ctx.font = '600 16px system-ui, -apple-system, Segoe UI, Roboto, Arial';
        ctx.fillText('Presiona Reiniciar o R', canvas.width / 2, canvas.height / 2 + 18);
      }

      state.needsRender = false;
    }

    function loop(ts) {
      state.rafId = requestAnimationFrame(loop);

      if (!state.running) {
        if (state.needsRender) render();
        return;
      }

      if (!state.lastTickAt) state.lastTickAt = ts;
      const elapsed = ts - state.lastTickAt;

      if (elapsed >= TICK_MS) {
        const ticks = Math.floor(elapsed / TICK_MS);
        state.lastTickAt += ticks * TICK_MS;
        step();
      }

      if (state.needsRender) render();
    }

    function onKeyDown(e) {
      const key = e.key.toLowerCase();

      if (key === 'arrowup' || key === 'w') setDirection('up');
      else if (key === 'arrowdown' || key === 's') setDirection('down');
      else if (key === 'arrowleft' || key === 'a') setDirection('left');
      else if (key === 'arrowright' || key === 'd') setDirection('right');
      else if (key === 'r') resetGame();

      if (key.startsWith('arrow')) e.preventDefault();
    }

    resetBtn.addEventListener('click', resetGame);
    window.addEventListener('keydown', onKeyDown, { passive: false });

    updateHud();
    resetGame();
  </script>
</body>
</html>