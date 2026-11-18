<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Snake Demo</title>
  <style>
    :root {
      color-scheme: dark;
    }
    body {
      margin: 0;
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji", "Segoe UI Emoji";
      background: #0b0f14;
      color: #e7eef8;
      display: grid;
      place-items: center;
      min-height: 100vh;
    }
    .wrap {
      width: min(92vw, 720px);
      display: grid;
      gap: 12px;
    }
    .hud {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 10px 12px;
      border: 1px solid #223044;
      border-radius: 10px;
      background: #0f1620;
    }
    .hud-left {
      display: flex;
      align-items: baseline;
      gap: 10px;
      flex-wrap: wrap;
    }
    .label {
      opacity: 0.8;
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    #score {
      font-variant-numeric: tabular-nums;
      font-size: 16px;
      font-weight: 700;
    }
    #status {
      font-size: 13px;
      opacity: 0.9;
    }
    button {
      appearance: none;
      border: 1px solid #2a3b55;
      background: #162234;
      color: #e7eef8;
      padding: 10px 12px;
      border-radius: 10px;
      cursor: pointer;
      font-weight: 700;
      letter-spacing: 0.02em;
    }
    button:hover {
      background: #1a2a42;
    }
    button:active {
      transform: translateY(1px);
    }
    .canvas-wrap {
      position: relative;
      border: 1px solid #223044;
      border-radius: 12px;
      overflow: hidden;
      background: #0f1620;
    }
    canvas {
      display: block;
      width: 100%;
      height: auto;
      image-rendering: pixelated;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hud">
      <div class="hud-left">
        <div><span class="label">Puntaje</span> <span id="score">0</span></div>
        <div id="status">Flechas para mover · Come para crecer</div>
      </div>
      <button id="restartBtn" type="button">Reiniciar</button>
    </div>

    <div class="canvas-wrap">
      <canvas id="game" width="600" height="600" aria-label="Snake"></canvas>
    </div>
  </div>

  <script>
    'use strict';

    const CELL_SIZE = 20;
    const GRID_COLS = 30;
    const GRID_ROWS = 30;
    const CANVAS_W = GRID_COLS * CELL_SIZE;
    const CANVAS_H = GRID_ROWS * CELL_SIZE;

    const TICK_MS = 110;

    const COLOR_BG = '#0f1620';
    const COLOR_GRID = '#142033';
    const COLOR_SNAKE = '#6ee7b7';
    const COLOR_SNAKE_HEAD = '#34d399';
    const COLOR_FOOD = '#f97316';
    const COLOR_TEXT = '#e7eef8';
    const COLOR_OVERLAY = 'rgba(0,0,0,0.55)';

    const DIRS = {
      UP: { x: 0, y: -1, key: 'ArrowUp' },
      DOWN: { x: 0, y: 1, key: 'ArrowDown' },
      LEFT: { x: -1, y: 0, key: 'ArrowLeft' },
      RIGHT: { x: 1, y: 0, key: 'ArrowRight' }
    };

    const OPPOSITE_KEY = {
      ArrowUp: 'ArrowDown',
      ArrowDown: 'ArrowUp',
      ArrowLeft: 'ArrowRight',
      ArrowRight: 'ArrowLeft'
    };

    const canvas = document.getElementById('game');
    const ctx = canvas.getContext('2d', { alpha: false });

    canvas.width = CANVAS_W;
    canvas.height = CANVAS_H;

    const scoreEl = document.getElementById('score');
    const statusEl = document.getElementById('status');
    const restartBtn = document.getElementById('restartBtn');

    const state = {
      snake: [],
      dirKey: 'ArrowRight',
      nextDirKey: 'ArrowRight',
      food: { x: 0, y: 0 },
      score: 0,
      gameOver: false,
      tickHandle: 0
    };

    function randInt(maxExclusive) {
      return Math.floor(Math.random() * maxExclusive);
    }

    function sameCell(a, b) {
      return a.x === b.x && a.y === b.y;
    }

    function inBounds(cell) {
      return cell.x >= 0 && cell.x < GRID_COLS && cell.y >= 0 && cell.y < GRID_ROWS;
    }

    function setDirection(dirKey) {
      if (!Object.prototype.hasOwnProperty.call(OPPOSITE_KEY, dirKey)) return;
      if (state.gameOver) return;

      const oppositeOfCurrent = OPPOSITE_KEY[state.dirKey];
      if (dirKey === oppositeOfCurrent) return;

      state.nextDirKey = dirKey;
    }

    function spawnFood() {
      const occupied = new Set(state.snake.map((c) => `${c.x},${c.y}`));
      let pos = { x: randInt(GRID_COLS), y: randInt(GRID_ROWS) };

      let guard = 0;
      while (occupied.has(`${pos.x},${pos.y}`) && guard < GRID_COLS * GRID_ROWS) {
        pos = { x: randInt(GRID_COLS), y: randInt(GRID_ROWS) };
        guard += 1;
      }

      state.food = pos;
    }

    function resetGame() {
      if (state.tickHandle) {
        clearInterval(state.tickHandle);
        state.tickHandle = 0;
      }

      const startX = Math.floor(GRID_COLS / 2);
      const startY = Math.floor(GRID_ROWS / 2);

      state.snake = [
        { x: startX, y: startY },
        { x: startX - 1, y: startY },
        { x: startX - 2, y: startY }
      ];

      state.dirKey = 'ArrowRight';
      state.nextDirKey = 'ArrowRight';
      state.score = 0;
      state.gameOver = false;

      spawnFood();
      updateHud();

      state.tickHandle = window.setInterval(step, TICK_MS);
      render();
    }

    function endGame() {
      state.gameOver = true;
      updateHud();
      render();
    }

    function updateHud() {
      scoreEl.textContent = String(state.score);
      statusEl.textContent = state.gameOver
        ? 'Game Over · Presiona Reiniciar'
        : 'Flechas para mover · Come para crecer';
    }

    function willHitSelf(nextHead) {
      return state.snake.some((seg) => sameCell(seg, nextHead));
    }

    function step() {
      if (state.gameOver) return;

      state.dirKey = state.nextDirKey;
      const dir = Object.values(DIRS).find((d) => d.key === state.dirKey);

      const head = state.snake[0];
      const nextHead = { x: head.x + dir.x, y: head.y + dir.y };

      if (!inBounds(nextHead) || willHitSelf(nextHead)) {
        endGame();
        return;
      }

      const ate = sameCell(nextHead, state.food);
      state.snake.unshift(nextHead);

      if (ate) {
        state.score += 1;
        spawnFood();
      } else {
        state.snake.pop();
      }

      updateHud();
      render();
    }

    function renderGrid() {
      ctx.strokeStyle = COLOR_GRID;
      ctx.lineWidth = 1;

      for (let x = 0; x <= GRID_COLS; x += 1) {
        ctx.beginPath();
        ctx.moveTo(x * CELL_SIZE + 0.5, 0);
        ctx.lineTo(x * CELL_SIZE + 0.5, CANVAS_H);
        ctx.stroke();
      }

      for (let y = 0; y <= GRID_ROWS; y += 1) {
        ctx.beginPath();
        ctx.moveTo(0, y * CELL_SIZE + 0.5);
        ctx.lineTo(CANVAS_W, y * CELL_SIZE + 0.5);
        ctx.stroke();
      }
    }

    function renderCell(cell, color) {
      ctx.fillStyle = color;
      ctx.fillRect(cell.x * CELL_SIZE, cell.y * CELL_SIZE, CELL_SIZE, CELL_SIZE);
    }

    function render() {
      ctx.fillStyle = COLOR_BG;
      ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);

      renderGrid();

      renderCell(state.food, COLOR_FOOD);

      for (let i = state.snake.length - 1; i >= 0; i -= 1) {
        const seg = state.snake[i];
        const color = i === 0 ? COLOR_SNAKE_HEAD : COLOR_SNAKE;
        renderCell(seg, color);
      }

      if (state.gameOver) {
        ctx.fillStyle = COLOR_OVERLAY;
        ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);

        ctx.fillStyle = COLOR_TEXT;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        ctx.font = '700 42px system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial';
        ctx.fillText('GAME OVER', CANVAS_W / 2, CANVAS_H / 2 - 18);

        ctx.font = '500 16px system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial';
        ctx.fillText('Presiona Reiniciar para jugar de nuevo', CANVAS_W / 2, CANVAS_H / 2 + 24);
      }
    }

    function handleKeydown(e) {
      const key = e.key;
      if (!Object.prototype.hasOwnProperty.call(OPPOSITE_KEY, key)) return;

      e.preventDefault();
      setDirection(key);
    }

    window.addEventListener('keydown', handleKeydown, { passive: false });

    restartBtn.addEventListener('click', () => resetGame());

    resetGame();
  </script>
</body>
</html>