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
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      background: #0b0f14;
      color: #e6edf3;
      display: grid;
      place-items: center;
      min-height: 100vh;
    }

    .wrap {
      width: min(92vw, 560px);
      display: grid;
      gap: 12px;
    }

    .hud {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 10px 12px;
      border: 1px solid #1f2a37;
      background: #0f1621;
      border-radius: 10px;
    }

    .hud .left {
      display: flex;
      gap: 16px;
      align-items: baseline;
      flex-wrap: wrap;
    }

    .label {
      opacity: 0.8;
      font-size: 12px;
      letter-spacing: 0.02em;
      text-transform: uppercase;
    }

    .value {
      font-weight: 700;
      font-variant-numeric: tabular-nums;
    }

    button {
      appearance: none;
      border: 1px solid #2a3a4d;
      background: #142033;
      color: #e6edf3;
      padding: 8px 12px;
      border-radius: 10px;
      cursor: pointer;
      font-weight: 600;
    }

    button:hover {
      background: #182844;
      border-color: #36506b;
    }

    button:active {
      transform: translateY(1px);
    }

    .canvas-wrap {
      position: relative;
      border-radius: 14px;
      overflow: hidden;
      border: 1px solid #1f2a37;
      background: #0b0f14;
    }

    canvas {
      display: block;
      width: 100%;
      height: auto;
      image-rendering: pixelated;
    }

    .help {
      opacity: 0.75;
      font-size: 12px;
      line-height: 1.4;
      padding: 0 4px;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hud">
      <div class="left">
        <div>
          <div class="label">Puntaje</div>
          <div class="value" id="scoreValue">0</div>
        </div>
        <div>
          <div class="label">Estado</div>
          <div class="value" id="statusValue">Jugando</div>
        </div>
      </div>
      <button id="resetBtn" type="button">Reiniciar</button>
    </div>

    <div class="canvas-wrap">
      <canvas id="gameCanvas" width="560" height="560"></canvas>
    </div>

    <div class="help">
      Controles: Flechas o WASD. No se permite reversa inmediata. Chocar con bordes o contigo mismo termina el juego.
    </div>
  </div>

  <script>
    'use strict';

    const CELL_SIZE = 20;
    const GRID_COLS = 28;
    const GRID_ROWS = 28;
    const CANVAS_WIDTH = GRID_COLS * CELL_SIZE;
    const CANVAS_HEIGHT = GRID_ROWS * CELL_SIZE;

    const TICK_MS = 110;

    const COLOR_BG = '#0b0f14';
    const COLOR_GRID = '#111a24';
    const COLOR_SNAKE_HEAD = '#22c55e';
    const COLOR_SNAKE_BODY = '#16a34a';
    const COLOR_FOOD = '#ef4444';
    const COLOR_TEXT = '#e6edf3';
    const COLOR_OVERLAY = 'rgba(0,0,0,0.55)';

    const DIR = {
      UP: { x: 0, y: -1, key: 'UP' },
      DOWN: { x: 0, y: 1, key: 'DOWN' },
      LEFT: { x: -1, y: 0, key: 'LEFT' },
      RIGHT: { x: 1, y: 0, key: 'RIGHT' }
    };

    const OPPOSITE = {
      UP: 'DOWN',
      DOWN: 'UP',
      LEFT: 'RIGHT',
      RIGHT: 'LEFT'
    };

    const canvas = document.getElementById('gameCanvas');
    const ctx = canvas.getContext('2d', { alpha: false });

    const scoreValue = document.getElementById('scoreValue');
    const statusValue = document.getElementById('statusValue');
    const resetBtn = document.getElementById('resetBtn');

    canvas.width = CANVAS_WIDTH;
    canvas.height = CANVAS_HEIGHT;

    const state = {
      running: true,
      gameOver: false,
      score: 0,
      direction: DIR.RIGHT,
      nextDirection: DIR.RIGHT,
      snake: [],
      food: { x: 0, y: 0 },
      lastTickAt: 0
    };

    function cellKey(x, y) {
      return `${x},${y}`;
    }

    function inBounds(x, y) {
      return x >= 0 && x < GRID_COLS && y >= 0 && y < GRID_ROWS;
    }

    function setDirection(newDir) {
      if (!newDir) return;
      if (state.gameOver) return;

      const currentKey = state.direction.key;
      if (OPPOSITE[currentKey] === newDir.key) return;
      state.nextDirection = newDir;
    }

    function resetGame() {
      state.running = true;
      state.gameOver = false;
      state.score = 0;

      const startX = Math.floor(GRID_COLS / 2);
      const startY = Math.floor(GRID_ROWS / 2);

      state.snake = [
        { x: startX, y: startY },
        { x: startX - 1, y: startY },
        { x: startX - 2, y: startY }
      ];

      state.direction = DIR.RIGHT;
      state.nextDirection = DIR.RIGHT;

      spawnFood();
      updateHud();
      render();
    }

    function spawnFood() {
      const occupied = new Set();
      for (const seg of state.snake) occupied.add(cellKey(seg.x, seg.y));

      const freeCells = [];
      for (let y = 0; y < GRID_ROWS; y++) {
        for (let x = 0; x < GRID_COLS; x++) {
          const key = cellKey(x, y);
          if (!occupied.has(key)) freeCells.push({ x, y });
        }
      }

      if (freeCells.length === 0) {
        state.gameOver = true;
        state.running = false;
        updateHud();
        return;
      }

      const idx = Math.floor(Math.random() * freeCells.length);
      state.food = freeCells[idx];
    }

    function updateHud() {
      scoreValue.textContent = String(state.score);
      statusValue.textContent = state.gameOver ? 'Game Over' : 'Jugando';
    }

    function endGame() {
      state.gameOver = true;
      state.running = false;
      updateHud();
    }

    function step() {
      if (!state.running || state.gameOver) return;

      state.direction = state.nextDirection;

      const head = state.snake[0];
      const newHead = { x: head.x + state.direction.x, y: head.y + state.direction.y };

      if (!inBounds(newHead.x, newHead.y)) {
        endGame();
        return;
      }

      const willEat = newHead.x === state.food.x && newHead.y === state.food.y;

      const tail = state.snake[state.snake.length - 1];
      const checkingLength = willEat ? state.snake.length : state.snake.length - 1;

      for (let i = 0; i < checkingLength; i++) {
        const seg = state.snake[i];
        if (seg.x === newHead.x && seg.y === newHead.y) {
          endGame();
          return;
        }
      }

      state.snake.unshift(newHead);

      if (willEat) {
        state.score += 1;
        spawnFood();
        updateHud();
      } else {
        state.snake.pop();
      }
    }

    function drawGrid() {
      ctx.strokeStyle = COLOR_GRID;
      ctx.lineWidth = 1;

      for (let x = 0; x <= GRID_COLS; x++) {
        const px = x * CELL_SIZE + 0.5;
        ctx.beginPath();
        ctx.moveTo(px, 0);
        ctx.lineTo(px, CANVAS_HEIGHT);
        ctx.stroke();
      }

      for (let y = 0; y <= GRID_ROWS; y++) {
        const py = y * CELL_SIZE + 0.5;
        ctx.beginPath();
        ctx.moveTo(0, py);
        ctx.lineTo(CANVAS_WIDTH, py);
        ctx.stroke();
      }
    }

    function fillCell(x, y, color) {
      ctx.fillStyle = color;
      ctx.fillRect(x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE);
    }

    function render() {
      ctx.fillStyle = COLOR_BG;
      ctx.fillRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);

      drawGrid();

      fillCell(state.food.x, state.food.y, COLOR_FOOD);

      for (let i = state.snake.length - 1; i >= 0; i--) {
        const seg = state.snake[i];
        fillCell(seg.x, seg.y, i === 0 ? COLOR_SNAKE_HEAD : COLOR_SNAKE_BODY);
      }

      if (state.gameOver) {
        ctx.fillStyle = COLOR_OVERLAY;
        ctx.fillRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);

        ctx.fillStyle = COLOR_TEXT;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        ctx.font = '700 34px system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif';
        ctx.fillText('GAME OVER', CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2 - 18);

        ctx.font = '500 16px system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif';
        ctx.fillText(`Puntaje: ${state.score}`, CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2 + 18);
        ctx.fillText('Presiona Reiniciar', CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2 + 42);
      }
    }

    function loop(ts) {
      if (!state.lastTickAt) state.lastTickAt = ts;

      const elapsed = ts - state.lastTickAt;
      if (elapsed >= TICK_MS) {
        state.lastTickAt = ts - (elapsed % TICK_MS);
        step();
        render();
      }

      requestAnimationFrame(loop);
    }

    function onKeyDown(e) {
      const key = e.key.toLowerCase();
      const map = {
        arrowup: DIR.UP,
        w: DIR.UP,
        arrowdown: DIR.DOWN,
        s: DIR.DOWN,
        arrowleft: DIR.LEFT,
        a: DIR.LEFT,
        arrowright: DIR.RIGHT,
        d: DIR.RIGHT
      };

      const dir = map[key];
      if (dir) {
        e.preventDefault();
        setDirection(dir);
      }

      if (key === 'r') resetGame();
    }

    resetBtn.addEventListener('click', resetGame);
    window.addEventListener('keydown', onKeyDown, { passive: false });

    resetGame();
    requestAnimationFrame(loop);
  </script>
</body>
</html>