<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Snake Demo 2.1-002</title>
  <style>
    :root {
      --bg: #0f1220;
      --panel: #171a2b;
      --text: #e9ecff;
      --muted: #aab0d6;
      --accent: #5be7c4;
      --danger: #ff5b7a;
      --border: rgba(255, 255, 255, 0.12);
      --shadow: rgba(0, 0, 0, 0.35);
    }

    * { box-sizing: border-box; }
    html, body { height: 100%; }
    body {
      margin: 0;
      background: radial-gradient(1000px 600px at 20% 0%, #1a2040 0%, var(--bg) 60%);
      color: var(--text);
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, "Noto Sans", Arial, "Apple Color Emoji", "Segoe UI Emoji";
      display: grid;
      place-items: center;
      padding: 16px;
    }

    .app {
      width: min(760px, 100%);
      display: grid;
      gap: 12px;
    }

    .hud {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 14px;
      background: color-mix(in srgb, var(--panel) 92%, black 8%);
      border: 1px solid var(--border);
      border-radius: 12px;
      box-shadow: 0 10px 30px var(--shadow);
    }

    .hud .left {
      display: grid;
      gap: 4px;
      min-width: 190px;
    }

    .titleRow {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 10px;
    }

    .title {
      font-weight: 700;
      letter-spacing: 0.2px;
    }

    .score {
      font-variant-numeric: tabular-nums;
      color: var(--accent);
      font-weight: 700;
    }

    .hint {
      font-size: 12px;
      color: var(--muted);
      line-height: 1.35;
    }

    .hud .right {
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
      justify-content: flex-end;
    }

    button {
      appearance: none;
      border: 1px solid var(--border);
      background: rgba(255, 255, 255, 0.04);
      color: var(--text);
      padding: 10px 12px;
      border-radius: 10px;
      cursor: pointer;
      font-weight: 600;
      transition: transform 120ms ease, background 120ms ease, border-color 120ms ease;
      user-select: none;
    }

    button:hover {
      background: rgba(255, 255, 255, 0.07);
      border-color: rgba(255, 255, 255, 0.18);
    }

    button:active { transform: translateY(1px); }
    button:focus-visible {
      outline: 2px solid color-mix(in srgb, var(--accent) 55%, white 45%);
      outline-offset: 2px;
    }

    .wrap {
      position: relative;
      display: grid;
      place-items: center;
      padding: 12px;
      background: color-mix(in srgb, var(--panel) 92%, black 8%);
      border: 1px solid var(--border);
      border-radius: 14px;
      box-shadow: 0 10px 30px var(--shadow);
    }

    canvas {
      display: block;
      border-radius: 10px;
      background: #0b0e1a;
      border: 1px solid rgba(255, 255, 255, 0.10);
      image-rendering: pixelated;
    }

    .srOnly {
      position: absolute !important;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }
  </style>
</head>
<body>
  <div class="app">
    <div class="hud" aria-label="HUD del juego">
      <div class="left">
        <div class="titleRow">
          <div class="title">Snake</div>
          <div class="score">Puntaje: <span id="scoreValue">0</span></div>
        </div>
        <div class="hint">Flechas/WASD para moverte. No puedes revertir dirección. Botón reiniciar siempre disponible.</div>
      </div>
      <div class="right">
        <button id="restartBtn" type="button">Reiniciar</button>
        <span class="srOnly" id="statusText" aria-live="polite"></span>
      </div>
    </div>

    <div class="wrap">
      <canvas id="gameCanvas" width="600" height="600" aria-label="Canvas del juego Snake"></canvas>
    </div>
  </div>

  <script>
    (() => {
      'use strict';

      const CANVAS_FIXED_SIZE = 600;
      const IS_RESPONSIVE = true;

      const CELL_SIZE = 20;
      const TICK_MS = 110;

      const COLORS = {
        bg: '#0b0e1a',
        grid: 'rgba(255,255,255,0.04)',
        snakeHead: '#5be7c4',
        snakeBody: 'rgba(91,231,196,0.82)',
        food: '#ff5b7a',
        text: 'rgba(233,236,255,0.92)',
        overlay: 'rgba(0,0,0,0.55)',
        border: 'rgba(255,255,255,0.12)'
      };

      const DIR = {
        up: { x: 0, y: -1 },
        down: { x: 0, y: 1 },
        left: { x: -1, y: 0 },
        right: { x: 1, y: 0 }
      };

      const KEY_TO_DIR = new Map([
        ['ArrowUp', DIR.up],
        ['KeyW', DIR.up],
        ['ArrowDown', DIR.down],
        ['KeyS', DIR.down],
        ['ArrowLeft', DIR.left],
        ['KeyA', DIR.left],
        ['ArrowRight', DIR.right],
        ['KeyD', DIR.right]
      ]);

      const canvas = document.getElementById('gameCanvas');
      const ctx = canvas.getContext('2d', { alpha: false });

      const scoreValueEl = document.getElementById('scoreValue');
      const statusTextEl = document.getElementById('statusText');
      const restartBtn = document.getElementById('restartBtn');

      const state = {
        cols: 0,
        rows: 0,
        canvasWidth: 0,
        canvasHeight: 0,

        snake: [],
        direction: DIR.right,
        pendingDirection: DIR.right,
        food: { x: 0, y: 0 },

        score: 0,
        isGameOver: false,

        lastTickAt: 0,
        accMs: 0,
        rafId: 0
      };

      const clampToCellMultiple = (valuePx) => Math.max(CELL_SIZE, Math.floor(valuePx / CELL_SIZE) * CELL_SIZE);

      const configureCanvas = () => {
        const dpr = Math.max(1, Math.floor(window.devicePixelRatio || 1));
        const cssSize = (() => {
          if (!IS_RESPONSIVE) return CANVAS_FIXED_SIZE;

          const hud = document.querySelector('.hud');
          const hudHeight = hud ? hud.getBoundingClientRect().height : 0;
          const verticalPadding = 16 * 2;
          const availableH = window.innerHeight - hudHeight - verticalPadding - 48;
          const availableW = window.innerWidth - verticalPadding;
          const target = Math.min(CANVAS_FIXED_SIZE, availableW, availableH);
          return clampToCellMultiple(Math.max(CELL_SIZE * 10, target));
        })();

        state.canvasWidth = cssSize;
        state.canvasHeight = cssSize;
        state.cols = Math.floor(cssSize / CELL_SIZE);
        state.rows = Math.floor(cssSize / CELL_SIZE);

        canvas.style.width = `${cssSize}px`;
        canvas.style.height = `${cssSize}px`;

        canvas.width = cssSize * dpr;
        canvas.height = cssSize * dpr;

        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      };

      const isOpposite = (a, b) => (a.x + b.x === 0) && (a.y + b.y === 0);

      const setDirection = (nextDir) => {
        if (!nextDir || state.isGameOver) return;

        const current = state.pendingDirection || state.direction;
        if (isOpposite(current, nextDir)) return;

        state.pendingDirection = nextDir;
      };

      const cellKey = (p) => `${p.x},${p.y}`;

      const isInside = (p) => p.x >= 0 && p.x < state.cols && p.y >= 0 && p.y < state.rows;

      const getNextHead = (dir) => {
        const head = state.snake[state.snake.length - 1];
        return { x: head.x + dir.x, y: head.y + dir.y };
      };

      const buildBodySet = (snakeArr) => {
        const set = new Set();
        for (let i = 0; i < snakeArr.length; i++) set.add(cellKey(snakeArr[i]));
        return set;
      };

      const spawnFood = () => {
        const occupied = buildBodySet(state.snake);
        const freeCells = state.cols * state.rows - occupied.size;
        if (freeCells <= 0) {
          state.isGameOver = true;
          statusTextEl.textContent = 'Ganaste. No quedan celdas libres.';
          return;
        }

        let x = 0;
        let y = 0;

        do {
          x = Math.floor(Math.random() * state.cols);
          y = Math.floor(Math.random() * state.rows);
        } while (occupied.has(`${x},${y}`));

        state.food = { x, y };
      };

      const resetGame = () => {
        state.score = 0;
        state.isGameOver = false;

        const startX = Math.floor(state.cols / 2);
        const startY = Math.floor(state.rows / 2);

        state.snake = [
          { x: startX - 1, y: startY },
          { x: startX, y: startY }
        ];

        state.direction = DIR.right;
        state.pendingDirection = DIR.right;

        spawnFood();

        state.lastTickAt = performance.now();
        state.accMs = 0;

        scoreValueEl.textContent = String(state.score);
        statusTextEl.textContent = 'Juego reiniciado.';
      };

      const endGame = (reason) => {
        state.isGameOver = true;
        statusTextEl.textContent = reason || 'Game Over.';
      };

      const step = () => {
        if (state.isGameOver) return;

        state.direction = state.pendingDirection;

        const nextHead = getNextHead(state.direction);
        if (!isInside(nextHead)) {
          endGame('Game Over: chocaste con el borde.');
          return;
        }

        const willEat = nextHead.x === state.food.x && nextHead.y === state.food.y;

        const collisionBody = willEat ? state.snake : state.snake.slice(1);
        const occupied = buildBodySet(collisionBody);
        if (occupied.has(cellKey(nextHead))) {
          endGame('Game Over: chocaste contigo mismo.');
          return;
        }

        state.snake.push(nextHead);

        if (willEat) {
          state.score += 1;
          scoreValueEl.textContent = String(state.score);
          spawnFood();
        } else {
          state.snake.shift();
        }
      };

      const drawRect = (x, y, w, h, fill) => {
        ctx.fillStyle = fill;
        ctx.fillRect(x, y, w, h);
      };

      const renderGrid = () => {
        ctx.strokeStyle = COLORS.grid;
        ctx.lineWidth = 1;

        for (let x = 0; x <= state.canvasWidth; x += CELL_SIZE) {
          ctx.beginPath();
          ctx.moveTo(x + 0.5, 0);
          ctx.lineTo(x + 0.5, state.canvasHeight);
          ctx.stroke();
        }

        for (let y = 0; y <= state.canvasHeight; y += CELL_SIZE) {
          ctx.beginPath();
          ctx.moveTo(0, y + 0.5);
          ctx.lineTo(state.canvasWidth, y + 0.5);
          ctx.stroke();
        }
      };

      const render = () => {
        drawRect(0, 0, state.canvasWidth, state.canvasHeight, COLORS.bg);
        renderGrid();

        const foodX = state.food.x * CELL_SIZE;
        const foodY = state.food.y * CELL_SIZE;
        drawRect(foodX + 3, foodY + 3, CELL_SIZE - 6, CELL_SIZE - 6, COLORS.food);

        for (let i = 0; i < state.snake.length; i++) {
          const p = state.snake[i];
          const x = p.x * CELL_SIZE;
          const y = p.y * CELL_SIZE;

          const isHead = i === state.snake.length - 1;
          const fill = isHead ? COLORS.snakeHead : COLORS.snakeBody;

          drawRect(x + 2, y + 2, CELL_SIZE - 4, CELL_SIZE - 4, fill);
        }

        if (state.isGameOver) {
          ctx.fillStyle = COLORS.overlay;
          ctx.fillRect(0, 0, state.canvasWidth, state.canvasHeight);

          ctx.fillStyle = COLORS.text;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';

          ctx.font = '700 40px system-ui, -apple-system, Segoe UI, Roboto, Arial';
          ctx.fillText('GAME OVER', state.canvasWidth / 2, state.canvasHeight / 2 - 18);

          ctx.font = '600 16px system-ui, -apple-system, Segoe UI, Roboto, Arial';
          ctx.fillText('Presiona Reiniciar para jugar de nuevo', state.canvasWidth / 2, state.canvasHeight / 2 + 20);
        }

        ctx.strokeStyle = COLORS.border;
        ctx.lineWidth = 1;
        ctx.strokeRect(0.5, 0.5, state.canvasWidth - 1, state.canvasHeight - 1);
      };

      const loop = (now) => {
        const dt = Math.min(250, now - state.lastTickAt);
        state.lastTickAt = now;
        state.accMs += dt;

        while (state.accMs >= TICK_MS) {
          step();
          state.accMs -= TICK_MS;
        }

        render();
        state.rafId = requestAnimationFrame(loop);
      };

      const onKeyDown = (e) => {
        const dir = KEY_TO_DIR.get(e.code);
        if (!dir) return;

        e.preventDefault();
        setDirection(dir);
      };

      const onResize = () => {
        const prevCols = state.cols;
        const prevRows = state.rows;

        configureCanvas();

        if (prevCols && prevRows && (prevCols !== state.cols || prevRows !== state.rows)) {
          resetGame();
        } else {
          render();
        }
      };

      const init = () => {
        configureCanvas();
        resetGame();

        window.addEventListener('keydown', onKeyDown, { passive: false });
        window.addEventListener('resize', onResize);

        restartBtn.addEventListener('click', () => resetGame());

        state.lastTickAt = performance.now();
        state.rafId = requestAnimationFrame(loop);
      };

      init();
    })();
  </script>
</body>
</html>