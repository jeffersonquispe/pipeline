<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Snake Demo</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0b1020;
      --panel: #0f1730;
      --text: #e8eefc;
      --muted: #a9b4d6;
      --border: rgba(255, 255, 255, 0.12);
      --btn: #1e2a55;
      --btnHover: #263468;
      --danger: #ff4d6d;
      --ok: #2dd4bf;
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: radial-gradient(1200px 800px at 20% 10%, #121c3d 0%, var(--bg) 55%, #070a14 100%);
      color: var(--text);
      font: 14px/1.35 system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, Arial;
      display: grid;
      place-items: center;
      min-height: 100vh;
      padding: 16px;
    }

    .wrap {
      width: min(900px, 100%);
      display: grid;
      gap: 12px;
    }

    .hud {
      display: flex;
      align-items: center;
      justify-content: space-between;
      background: linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.03));
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 10px 12px;
      gap: 10px;
      flex-wrap: wrap;
    }

    .hud-left, .hud-right {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }

    .chip {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 7px 10px;
      border-radius: 999px;
      border: 1px solid var(--border);
      background: rgba(0,0,0,0.25);
      color: var(--text);
      user-select: none;
      white-space: nowrap;
    }

    .chip .label { color: var(--muted); }
    .chip .value { font-variant-numeric: tabular-nums; }

    button {
      appearance: none;
      border: 1px solid var(--border);
      background: var(--btn);
      color: var(--text);
      padding: 9px 12px;
      border-radius: 10px;
      cursor: pointer;
      font-weight: 600;
      letter-spacing: 0.2px;
      transition: background 120ms ease, transform 80ms ease;
    }
    button:hover { background: var(--btnHover); }
    button:active { transform: translateY(1px); }
    button:focus-visible { outline: 2px solid rgba(45,212,191,0.55); outline-offset: 2px; }

    .stage {
      position: relative;
      border-radius: 14px;
      border: 1px solid var(--border);
      overflow: hidden;
      background: rgba(0,0,0,0.2);
    }

    canvas {
      display: block;
      width: 100%;
      height: auto;
      image-rendering: pixelated;
      background: transparent;
    }

    .help {
      color: var(--muted);
      font-size: 12px;
      margin-left: 2px;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hud" aria-label="HUD">
      <div class="hud-left">
        <div class="chip" aria-label="Puntaje">
          <span class="label">Puntaje</span>
          <span class="value" id="scoreValue">0</span>
        </div>
        <div class="chip" aria-label="Estado">
          <span class="label">Estado</span>
          <span class="value" id="statusText">Listo</span>
        </div>
        <div class="help">Controles: Flechas / WASD. Reinicia con el botón.</div>
      </div>
      <div class="hud-right">
        <button id="resetBtn" type="button">Reiniciar</button>
      </div>
    </div>

    <div class="stage">
      <canvas id="gameCanvas" width="600" height="420" aria-label="Juego Snake"></canvas>
    </div>
  </div>

  <script>
    'use strict';

    // ===== Constantes (sin números mágicos) =====
    const CELL_SIZE = 20;
    const TICK_MS = 120;

    const GRID_COLS = 30; // 600 / 20
    const GRID_ROWS = 21; // 420 / 20

    const COLOR_BG = '#0b1020';
    const COLOR_GRID = 'rgba(255,255,255,0.06)';
    const COLOR_SNAKE_HEAD = '#2dd4bf';
    const COLOR_SNAKE_BODY = '#1aa39a';
    const COLOR_FOOD = '#ff4d6d';
    const COLOR_TEXT = 'rgba(232,238,252,0.95)';
    const COLOR_OVERLAY = 'rgba(0,0,0,0.55)';

    const DIR = Object.freeze({
      up: { x: 0, y: -1, name: 'up' },
      down: { x: 0, y: 1, name: 'down' },
      left: { x: -1, y: 0, name: 'left' },
      right: { x: 1, y: 0, name: 'right' }
    });

    // ===== DOM / Canvas =====
    const canvas = document.getElementById('gameCanvas');
    const ctx = canvas.getContext('2d', { alpha: false });

    const scoreValueEl = document.getElementById('scoreValue');
    const statusTextEl = document.getElementById('statusText');
    const resetBtn = document.getElementById('resetBtn');

    // ===== Estado del juego =====
    const state = {
      cellSize: CELL_SIZE,
      cols: GRID_COLS,
      rows: GRID_ROWS,

      snake: [],
      dir: DIR.right,
      nextDir: DIR.right,

      food: { x: 0, y: 0 },
      score: 0,
      gameOver: false,

      tickMs: TICK_MS,
      timerId: null,
      lastTick: 0,

      moved: false,

      colors: {
        bg: COLOR_BG,
        grid: COLOR_GRID,
        snakeHead: COLOR_SNAKE_HEAD,
        snakeBody: COLOR_SNAKE_BODY,
        food: COLOR_FOOD,
        text: COLOR_TEXT,
        overlay: COLOR_OVERLAY
      }
    };

    // ===== Utilidades =====
    const randInt = (min, maxInclusive) => {
      const r = Math.random() * (maxInclusive - min + 1);
      return min + Math.floor(r);
    };

    const sameCell = (a, b) => a.x === b.x && a.y === b.y;

    const isOpposite = (a, b) => a.x + b.x === 0 && a.y + b.y === 0;

    const inBounds = (cell) =>
      cell.x >= 0 && cell.x < state.cols && cell.y >= 0 && cell.y < state.rows;

    const snakeOccupies = (cell, segments = state.snake) => segments.some((s) => sameCell(s, cell));

    // ===== HUD =====
    const updateHud = () => {
      scoreValueEl.textContent = String(state.score);

      let status = 'Listo';
      if (state.gameOver) status = 'Game Over';
      else if (state.moved) status = 'Jugando';

      statusTextEl.textContent = status;
    };

    // ===== Juego =====
    const spawnFood = () => {
      const maxAttempts = state.cols * state.rows * 2;
      for (let i = 0; i < maxAttempts; i++) {
        const candidate = { x: randInt(0, state.cols - 1), y: randInt(0, state.rows - 1) };
        if (!snakeOccupies(candidate)) {
          state.food = candidate;
          return;
        }
      }
      // Si el tablero está lleno, mantener la comida donde está; el siguiente step terminará por colisión/llenado.
    };

    const resetGame = () => {
      if (state.timerId !== null) {
        clearInterval(state.timerId);
        state.timerId = null;
      }

      state.score = 0;
      state.gameOver = false;
      state.lastTick = 0;
      state.tickMs = TICK_MS;
      state.moved = false;

      const startX = Math.floor(state.cols / 2);
      const startY = Math.floor(state.rows / 2);

      // Cabeza al inicio del array
      state.snake = [
        { x: startX, y: startY },
        { x: startX - 1, y: startY },
        { x: startX - 2, y: startY }
      ];

      state.dir = DIR.right;
      state.nextDir = DIR.right;

      spawnFood();
      updateHud();
      render();

      state.timerId = setInterval(() => {
        step();
        render();
      }, state.tickMs);
    };

    const setDirection = (dirName) => {
      const desired = DIR[dirName];
      if (!desired || state.gameOver) return;

      // No permitir reversa inmediata
      if (isOpposite(desired, state.dir)) return;

      state.nextDir = desired;
    };

    const step = () => {
      if (state.gameOver) return;

      state.dir = state.nextDir;

      const head = state.snake[0];
      const nextHead = { x: head.x + state.dir.x, y: head.y + state.dir.y };

      if (!inBounds(nextHead)) {
        state.gameOver = true;
        updateHud();
        return;
      }

      const ate = sameCell(nextHead, state.food);

      // Corrección: si no come, puede entrar en la celda de la cola (que se movería)
      const bodyToCheck = ate ? state.snake : state.snake.slice(0, -1);
      const hitSelf = snakeOccupies(nextHead, bodyToCheck);
      if (hitSelf) {
        state.gameOver = true;
        updateHud();
        return;
      }

      state.snake.unshift(nextHead);

      if (ate) {
        state.score += 1;
        spawnFood();
      } else {
        state.snake.pop();
      }

      state.moved = true;
      updateHud();
    };

    // ===== Render =====
    const renderGrid = () => {
      ctx.strokeStyle = state.colors.grid;
      ctx.lineWidth = 1;

      for (let x = 0; x <= state.cols; x++) {
        const px = x * state.cellSize + 0.5;
        ctx.beginPath();
        ctx.moveTo(px, 0);
        ctx.lineTo(px, state.rows * state.cellSize);
        ctx.stroke();
      }

      for (let y = 0; y <= state.rows; y++) {
        const py = y * state.cellSize + 0.5;
        ctx.beginPath();
        ctx.moveTo(0, py);
        ctx.lineTo(state.cols * state.cellSize, py);
        ctx.stroke();
      }
    };

    const fillCell = (cell, color, inset = 1) => {
      const x = cell.x * state.cellSize;
      const y = cell.y * state.cellSize;
      ctx.fillStyle = color;
      ctx.fillRect(x + inset, y + inset, state.cellSize - inset * 2, state.cellSize - inset * 2);
    };

    const render = () => {
      // Fondo
      ctx.fillStyle = state.colors.bg;
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      renderGrid();

      // Comida
      fillCell(state.food, state.colors.food, 3);

      // Serpiente
      state.snake.forEach((seg, i) => {
        fillCell(seg, i === 0 ? state.colors.snakeHead : state.colors.snakeBody, 2);
      });

      // Overlay Game Over
      if (state.gameOver) {
        ctx.fillStyle = state.colors.overlay;
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        ctx.fillStyle = state.colors.text;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        ctx.font = '700 34px system-ui, -apple-system, Segoe UI, Roboto, Arial';
        ctx.fillText('GAME OVER', canvas.width / 2, canvas.height / 2 - 18);

        ctx.font = '500 16px system-ui, -apple-system, Segoe UI, Roboto, Arial';
        ctx.fillText('Pulsa "Reiniciar" para jugar otra vez.', canvas.width / 2, canvas.height / 2 + 18);
      }
    };

    // ===== Controles =====
    const onKeyDown = (e) => {
      const key = e.key.toLowerCase();
      const map = {
        arrowup: 'up',
        w: 'up',
        arrowdown: 'down',
        s: 'down',
        arrowleft: 'left',
        a: 'left',
        arrowright: 'right',
        d: 'right'
      };

      const dirName = map[key];
      if (!dirName) return;

      e.preventDefault();
      setDirection(dirName);
    };

    document.addEventListener('keydown', onKeyDown, { passive: false });
    resetBtn.addEventListener('click', () => resetGame());

    // Asegurar tamaño de canvas compatible con grid
    canvas.width = state.cols * state.cellSize;
    canvas.height = state.rows * state.cellSize;

    resetGame();
  </script>
</body>
</html>