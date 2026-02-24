"""
🎮 RL Tools for DevDuck — Learn anything with Reinforcement Learning.

Uses Stable-Baselines3 + Gymnasium to give DevDuck the power to:
1. Train RL agents on any Gymnasium environment
2. Create CUSTOM environments from Python reward functions
3. Evaluate trained policies
4. Run inference (watch a trained agent act)
5. Manage saved models
6. Hyperparameter sweep
7. Curriculum learning (progressive difficulty)

The killer feature: `create_env` lets you define a reward function in plain Python,
wrap it as a Gymnasium env, and train an RL agent on it — all from natural language.

Examples:
    # Train on a built-in env
    rl(action="train", env_id="CartPole-v1", algorithm="PPO", total_timesteps=50000)

    # Create a custom env and train on it
    rl(action="create_env", env_name="balance", reward_code="...", obs_dim=4, act_dim=1)
    rl(action="train", env_id="custom:balance", algorithm="SAC", total_timesteps=100000)

    # Evaluate a trained model
    rl(action="eval", model_path="rl_models/CartPole-v1_PPO/best_model", n_episodes=20)

    # Watch it play
    rl(action="play", model_path="rl_models/CartPole-v1_PPO/best_model", env_id="CartPole-v1")

    # List available envs
    rl(action="list_envs")

    # Hyperparameter sweep
    rl(action="sweep", env_id="LunarLander-v3", algorithm="PPO", n_trials=10)
"""

import json
import os
import sys
import time
import threading
import tempfile
import importlib
import traceback
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from strands import tool

# ─── Constants ───────────────────────────────────────────────────────────────

RL_MODELS_DIR = Path(os.getenv("DEVDUCK_RL_MODELS_DIR", "./rl_models"))
RL_CUSTOM_ENVS_DIR = Path(os.getenv("DEVDUCK_RL_ENVS_DIR", "./rl_envs"))
RL_LOGS_DIR = Path(os.getenv("DEVDUCK_RL_LOGS_DIR", "./rl_logs"))

# Supported algorithms
ALGORITHMS = {
    "PPO": "stable_baselines3.PPO",
    "A2C": "stable_baselines3.A2C",
    "DQN": "stable_baselines3.DQN",
    "SAC": "stable_baselines3.SAC",
    "TD3": "stable_baselines3.TD3",
    "DDPG": "stable_baselines3.DDPG",
}

# ─── Custom Environment Registry ────────────────────────────────────────────

_custom_envs: Dict[str, Any] = {}


def _get_algorithm_class(name: str):
    """Dynamically import an SB3 algorithm class."""
    name = name.upper()
    if name not in ALGORITHMS:
        raise ValueError(f"Unknown algorithm: {name}. Available: {list(ALGORITHMS.keys())}")
    module_path, class_name = ALGORITHMS[name].rsplit(".", 1)
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


def _make_env(env_id: str, seed: int = None, render_mode: str = None):
    """Create a Gymnasium environment by ID, supporting custom envs."""
    import gymnasium as gym

    if env_id.startswith("custom:"):
        custom_name = env_id.split(":", 1)[1]
        if custom_name not in _custom_envs:
            # Try loading from disk
            env_file = RL_CUSTOM_ENVS_DIR / f"{custom_name}.py"
            if env_file.exists():
                _load_custom_env(custom_name, env_file)
            else:
                raise ValueError(
                    f"Custom env '{custom_name}' not found. "
                    f"Create it first with action='create_env'"
                )
        env_cls = _custom_envs[custom_name]
        env = env_cls(render_mode=render_mode)
    else:
        env = gym.make(env_id, render_mode=render_mode)

    if seed is not None:
        env.reset(seed=seed)
    return env


def _load_custom_env(name: str, path: Path):
    """Load a custom environment class from a .py file."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(f"rl_env_{name}", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Find the env class (should be the one inheriting from gymnasium.Env)
    import gymnasium as gym

    for attr_name in dir(mod):
        attr = getattr(mod, attr_name)
        if isinstance(attr, type) and issubclass(attr, gym.Env) and attr is not gym.Env:
            _custom_envs[name] = attr
            return

    raise ValueError(f"No gymnasium.Env subclass found in {path}")


# ─── Training Progress Callback ─────────────────────────────────────────────

class _ProgressCallback:
    """Simple training progress tracker."""

    def __init__(self, total_timesteps: int, print_freq: int = 10000):
        from stable_baselines3.common.callbacks import BaseCallback

        self.total = total_timesteps
        self.print_freq = print_freq
        self.start_time = time.time()
        self.best_reward = -float("inf")
        self.episode_rewards = []

        class Inner(BaseCallback):
            def __init__(inner_self, outer=self, verbose=0):
                super().__init__(verbose)
                inner_self.outer = outer

            def _on_step(inner_self) -> bool:
                if inner_self.num_timesteps % inner_self.outer.print_freq == 0:
                    elapsed = time.time() - inner_self.outer.start_time
                    fps = inner_self.num_timesteps / max(elapsed, 1)
                    pct = (inner_self.num_timesteps / inner_self.outer.total) * 100
                    print(
                        f"  ⏳ {inner_self.num_timesteps:,}/{inner_self.outer.total:,} "
                        f"({pct:.0f}%) | {fps:.0f} fps | {elapsed:.0f}s",
                        flush=True,
                    )
                return True

        self.callback_cls = Inner

    def get(self):
        return self.callback_cls()


# ─── Core Actions ────────────────────────────────────────────────────────────

def _action_train(
    env_id: str,
    algorithm: str = "PPO",
    total_timesteps: int = 100000,
    seed: int = 42,
    hyperparams: Dict[str, Any] = None,
    save_name: str = None,
    n_envs: int = 1,
    eval_freq: int = 10000,
    device: str = "auto",
) -> Dict[str, Any]:
    """Train an RL agent."""
    from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv
    from stable_baselines3.common.callbacks import EvalCallback
    from stable_baselines3.common.monitor import Monitor

    algo_cls = _get_algorithm_class(algorithm)

    # Create vectorized training env
    def make_train_env(i):
        def _init():
            env = _make_env(env_id, seed=seed + i)
            return Monitor(env)
        return _init

    if n_envs > 1:
        train_env = SubprocVecEnv([make_train_env(i) for i in range(n_envs)])
    else:
        train_env = DummyVecEnv([make_train_env(0)])

    # Create eval env
    eval_env = DummyVecEnv([lambda: Monitor(_make_env(env_id, seed=seed + 1000))])

    # Model save path
    name = save_name or f"{env_id.replace(':', '_').replace('/', '_')}_{algorithm}"
    model_dir = RL_MODELS_DIR / name
    model_dir.mkdir(parents=True, exist_ok=True)
    log_dir = RL_LOGS_DIR / name
    log_dir.mkdir(parents=True, exist_ok=True)

    # Hyperparameters
    hp = hyperparams or {}
    hp.setdefault("verbose", 1)
    hp.setdefault("device", device)
    hp.setdefault("seed", seed)

    # Check if algorithm supports continuous/discrete action space
    # DQN only works with discrete action spaces
    test_env = _make_env(env_id, seed=seed)
    import gymnasium as gym
    action_space = test_env.action_space
    obs_space = test_env.observation_space
    test_env.close()

    if algorithm.upper() == "DQN" and not isinstance(action_space, gym.spaces.Discrete):
        return {
            "status": "error",
            "content": [{"text": f"❌ DQN requires discrete actions, but {env_id} has {type(action_space).__name__}. Use PPO, SAC, TD3, or DDPG instead."}],
        }

    if algorithm.upper() in ("SAC", "TD3", "DDPG") and isinstance(action_space, gym.spaces.Discrete):
        return {
            "status": "error",
            "content": [{"text": f"❌ {algorithm} requires continuous actions, but {env_id} has Discrete. Use PPO, A2C, or DQN instead."}],
        }

    print(f"\n🎮 Training {algorithm} on {env_id}")
    print(f"   Steps: {total_timesteps:,} | Envs: {n_envs} | Seed: {seed}")
    print(f"   Save: {model_dir}")
    print(f"   Action space: {action_space}")
    print(f"   Obs space: {obs_space}")
    if hp:
        print(f"   Hyperparams: {json.dumps({k: str(v) for k, v in hp.items() if k not in ('verbose', 'device', 'seed')}, indent=2)}")
    print()

    # Create model
    start_time = time.time()
    model = algo_cls("MlpPolicy", train_env, tensorboard_log=str(log_dir), **hp)

    # Callbacks
    progress = _ProgressCallback(total_timesteps)
    eval_callback = EvalCallback(
        eval_env,
        best_model_save_path=str(model_dir / "best"),
        log_path=str(log_dir),
        eval_freq=max(eval_freq // n_envs, 1),
        n_eval_episodes=10,
        deterministic=True,
    )

    # Train
    model.learn(
        total_timesteps=total_timesteps,
        callback=[progress.get(), eval_callback],
        progress_bar=False,
    )

    # Save final model
    final_path = model_dir / "final_model"
    model.save(str(final_path))

    elapsed = time.time() - start_time
    fps = total_timesteps / max(elapsed, 1)

    # Load eval results
    eval_results = {}
    eval_log = log_dir / "evaluations.npz"
    if eval_log.exists():
        import numpy as np
        data = np.load(str(eval_log))
        if "results" in data:
            results = data["results"]
            eval_results = {
                "best_mean_reward": float(results.mean(axis=1).max()),
                "final_mean_reward": float(results[-1].mean()) if len(results) > 0 else 0,
                "best_std": float(results[results.mean(axis=1).argmax()].std()),
            }

    train_env.close()
    eval_env.close()

    summary = (
        f"✅ Training complete!\n"
        f"   Algorithm: {algorithm}\n"
        f"   Environment: {env_id}\n"
        f"   Total steps: {total_timesteps:,}\n"
        f"   Time: {elapsed:.1f}s ({fps:.0f} fps)\n"
        f"   Best mean reward: {eval_results.get('best_mean_reward', 'N/A')}\n"
        f"   Final mean reward: {eval_results.get('final_mean_reward', 'N/A')}\n"
        f"   Model saved: {final_path}\n"
        f"   Best model: {model_dir / 'best' / 'best_model'}\n"
        f"   TensorBoard: tensorboard --logdir {log_dir}"
    )

    return {
        "status": "success",
        "content": [
            {"text": summary},
            {"json": {
                "model_path": str(final_path),
                "best_model_path": str(model_dir / "best" / "best_model"),
                "log_dir": str(log_dir),
                "elapsed_seconds": elapsed,
                "fps": fps,
                **eval_results,
            }},
        ],
    }


def _action_eval(
    model_path: str,
    env_id: str = None,
    algorithm: str = None,
    n_episodes: int = 20,
    deterministic: bool = True,
    seed: int = 42,
    render: bool = False,
) -> Dict[str, Any]:
    """Evaluate a trained model."""
    import numpy as np

    # Auto-detect algorithm from path if not specified
    if algorithm is None:
        for algo_name in ALGORITHMS:
            if algo_name in str(model_path).upper():
                algorithm = algo_name
                break
        if algorithm is None:
            algorithm = "PPO"  # Default fallback

    # Auto-detect env from path if not specified
    if env_id is None:
        # Try to extract from model directory name
        model_dir = Path(model_path).parent
        for part in [model_dir.name, model_dir.parent.name]:
            for algo_name in ALGORITHMS:
                if part.endswith(f"_{algo_name}"):
                    env_id = part[: -(len(algo_name) + 1)]
                    break
            if env_id:
                break

    if env_id is None:
        return {
            "status": "error",
            "content": [{"text": "❌ Could not auto-detect env_id. Please specify it."}],
        }

    algo_cls = _get_algorithm_class(algorithm)
    model = algo_cls.load(model_path)

    render_mode = "human" if render else None
    env = _make_env(env_id, seed=seed, render_mode=render_mode)

    print(f"\n🎯 Evaluating {algorithm} on {env_id} ({n_episodes} episodes)")

    episode_rewards = []
    episode_lengths = []

    for ep in range(n_episodes):
        obs, info = env.reset(seed=seed + ep)
        done = False
        total_reward = 0
        steps = 0

        while not done:
            action, _ = model.predict(obs, deterministic=deterministic)
            obs, reward, terminated, truncated, info = env.step(action)
            total_reward += reward
            steps += 1
            done = terminated or truncated

        episode_rewards.append(total_reward)
        episode_lengths.append(steps)

        if (ep + 1) % max(1, n_episodes // 5) == 0:
            print(f"  Episode {ep + 1}/{n_episodes}: reward={total_reward:.2f}, steps={steps}")

    env.close()

    rewards = np.array(episode_rewards)
    lengths = np.array(episode_lengths)

    summary = (
        f"✅ Evaluation complete!\n"
        f"   Episodes: {n_episodes}\n"
        f"   Mean reward: {rewards.mean():.2f} ± {rewards.std():.2f}\n"
        f"   Min/Max reward: {rewards.min():.2f} / {rewards.max():.2f}\n"
        f"   Mean episode length: {lengths.mean():.1f} ± {lengths.std():.1f}\n"
        f"   Success rate (reward > 0): {(rewards > 0).mean() * 100:.1f}%"
    )

    return {
        "status": "success",
        "content": [
            {"text": summary},
            {"json": {
                "mean_reward": float(rewards.mean()),
                "std_reward": float(rewards.std()),
                "min_reward": float(rewards.min()),
                "max_reward": float(rewards.max()),
                "mean_length": float(lengths.mean()),
                "success_rate": float((rewards > 0).mean()),
                "all_rewards": [float(r) for r in rewards],
            }},
        ],
    }


def _action_play(
    model_path: str,
    env_id: str = None,
    algorithm: str = None,
    n_episodes: int = 3,
    seed: int = 42,
    record_video: bool = False,
    video_path: str = None,
) -> Dict[str, Any]:
    """Watch a trained agent play (render or record video)."""

    if algorithm is None:
        for algo_name in ALGORITHMS:
            if algo_name in str(model_path).upper():
                algorithm = algo_name
                break
        if algorithm is None:
            algorithm = "PPO"

    if env_id is None:
        model_dir = Path(model_path).parent
        for part in [model_dir.name, model_dir.parent.name]:
            for algo_name in ALGORITHMS:
                if part.endswith(f"_{algo_name}"):
                    env_id = part[: -(len(algo_name) + 1)]
                    break
            if env_id:
                break

    if env_id is None:
        return {
            "status": "error",
            "content": [{"text": "❌ Could not auto-detect env_id. Please specify it."}],
        }

    algo_cls = _get_algorithm_class(algorithm)
    model = algo_cls.load(model_path)

    if record_video:
        import gymnasium as gym
        from gymnasium.wrappers import RecordVideo

        vpath = video_path or f"rl_videos/{env_id}_{algorithm}"
        Path(vpath).mkdir(parents=True, exist_ok=True)
        env = gym.make(env_id, render_mode="rgb_array")
        env = RecordVideo(env, video_folder=vpath, episode_trigger=lambda x: True)
    else:
        env = _make_env(env_id, seed=seed, render_mode="human")

    print(f"\n🎬 Playing {algorithm} on {env_id} ({n_episodes} episodes)")

    for ep in range(n_episodes):
        obs, info = env.reset(seed=seed + ep)
        done = False
        total_reward = 0
        steps = 0

        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = env.step(action)
            total_reward += reward
            steps += 1
            done = terminated or truncated

        print(f"  Episode {ep + 1}: reward={total_reward:.2f}, steps={steps}")

    env.close()

    text = f"✅ Played {n_episodes} episodes of {env_id}"
    if record_video:
        text += f"\n   Videos saved to: {vpath}"

    return {"status": "success", "content": [{"text": text}]}


def _action_create_env(
    env_name: str,
    reward_code: str,
    obs_dim: int = 4,
    act_dim: int = 1,
    act_type: str = "continuous",
    max_steps: int = 1000,
    description: str = "",
    reset_code: str = None,
    step_code: str = None,
) -> Dict[str, Any]:
    """Create a custom Gymnasium environment from Python code.

    You can provide either:
    1. Just `reward_code` — a simple reward function. The env auto-manages state as a numpy array.
    2. Full `step_code` + `reset_code` — complete control over dynamics.

    reward_code signature: def reward(state, action) -> (next_state, reward, terminated)
    step_code signature:   def step(self, action) -> (obs, reward, terminated, truncated, info)
    reset_code signature:  def reset(self, seed=None, options=None) -> (obs, info)
    """
    RL_CUSTOM_ENVS_DIR.mkdir(parents=True, exist_ok=True)

    if act_type == "continuous":
        action_space_code = f"spaces.Box(low=-1.0, high=1.0, shape=({act_dim},), dtype=np.float32)"
    else:
        action_space_code = f"spaces.Discrete({act_dim})"

    # Build the environment class
    if step_code and reset_code:
        # Full custom env
        env_code = f'''"""Custom RL Environment: {env_name}
{description}
Generated by DevDuck RL Tools on {datetime.now().isoformat()}
"""
import numpy as np
import gymnasium as gym
from gymnasium import spaces


class {env_name.title().replace("_", "")}Env(gym.Env):
    """Custom environment: {env_name}"""

    metadata = {{"render_modes": ["human", "rgb_array"], "render_fps": 30}}

    def __init__(self, render_mode=None):
        super().__init__()
        self.render_mode = render_mode
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=({obs_dim},), dtype=np.float32)
        self.action_space = {action_space_code}
        self.max_steps = {max_steps}
        self.current_step = 0
        self.state = np.zeros({obs_dim}, dtype=np.float32)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0
{_indent(reset_code, 8)}

    def step(self, action):
        self.current_step += 1
{_indent(step_code, 8)}

    def render(self):
        if self.render_mode == "rgb_array":
            # Simple visualization: 64x64 grayscale from state
            img = np.zeros((64, 64, 3), dtype=np.uint8)
            for i, val in enumerate(self.state[:min(len(self.state), 64)]):
                col = int(np.clip(abs(val) * 255, 0, 255))
                img[i * (64 // {obs_dim}):(i + 1) * (64 // {obs_dim}), :, :] = col
            return img
        return None
'''
    else:
        # Simple reward-only env (auto state management)
        env_code = f'''"""Custom RL Environment: {env_name}
{description}
Generated by DevDuck RL Tools on {datetime.now().isoformat()}
"""
import numpy as np
import gymnasium as gym
from gymnasium import spaces


# User-defined reward function
{reward_code}


class {env_name.title().replace("_", "")}Env(gym.Env):
    """Custom environment: {env_name}
    Uses auto-managed state with user-defined reward function.
    """

    metadata = {{"render_modes": ["human", "rgb_array"], "render_fps": 30}}

    def __init__(self, render_mode=None):
        super().__init__()
        self.render_mode = render_mode
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=({obs_dim},), dtype=np.float32)
        self.action_space = {action_space_code}
        self.max_steps = {max_steps}
        self.current_step = 0
        self.state = np.zeros({obs_dim}, dtype=np.float32)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0
        self.state = self.np_random.uniform(low=-0.5, high=0.5, size=({obs_dim},)).astype(np.float32)
        return self.state.copy(), {{}}

    def step(self, action):
        self.current_step += 1
        action = np.asarray(action, dtype=np.float32).flatten()

        # Call user reward function
        next_state, rew, terminated = reward(self.state, action)
        self.state = np.asarray(next_state, dtype=np.float32)

        truncated = self.current_step >= self.max_steps
        return self.state.copy(), float(rew), bool(terminated), truncated, {{}}

    def render(self):
        if self.render_mode == "rgb_array":
            img = np.zeros((64, 64, 3), dtype=np.uint8)
            for i, val in enumerate(self.state[:min(len(self.state), 64)]):
                col = int(np.clip(abs(val) * 255, 0, 255))
                img[i * (64 // max({obs_dim}, 1)):(i + 1) * (64 // max({obs_dim}, 1)), :, :] = col
            return img
        return None
'''

    # Save the env file
    env_file = RL_CUSTOM_ENVS_DIR / f"{env_name}.py"
    with open(env_file, "w") as f:
        f.write(env_code)

    # Load it immediately
    try:
        _load_custom_env(env_name, env_file)

        # Validate it works
        test_env = _custom_envs[env_name](render_mode=None)
        obs, info = test_env.reset(seed=42)
        action = test_env.action_space.sample()
        obs2, rew, term, trunc, info = test_env.step(action)
        test_env.close()

        summary = (
            f"✅ Custom environment '{env_name}' created and validated!\n"
            f"   File: {env_file}\n"
            f"   Obs space: Box({obs_dim},)\n"
            f"   Action space: {'Box' if act_type == 'continuous' else 'Discrete'}({act_dim})\n"
            f"   Max steps: {max_steps}\n"
            f"   Test: obs={obs[:3]}..., reward={rew:.4f}\n"
            f"\n   Train with: rl(action='train', env_id='custom:{env_name}', algorithm='PPO')"
        )

        return {"status": "success", "content": [{"text": summary}]}

    except Exception as e:
        return {
            "status": "error",
            "content": [{"text": f"❌ Environment validation failed:\n{traceback.format_exc()}\n\nFile saved at {env_file} — fix the code and try again."}],
        }


def _action_list_envs(category: str = None) -> Dict[str, Any]:
    """List available environments."""
    import gymnasium as gym

    # Built-in Gymnasium envs
    all_envs = gym.envs.registry.keys()

    categories = {
        "classic": ["CartPole", "MountainCar", "Pendulum", "Acrobot", "LunarLander"],
        "box2d": ["BipedalWalker", "CarRacing", "LunarLander"],
        "mujoco": ["Ant", "HalfCheetah", "Hopper", "Humanoid", "Reacher", "Swimmer", "Walker2d", "InvertedPendulum"],
        "atari": ["Breakout", "Pong", "SpaceInvaders"],
    }

    lines = ["🎮 Available Environments:\n"]

    if category and category in categories:
        # Filter by category
        keywords = categories[category]
        envs = [e for e in sorted(all_envs) if any(k in e for k in keywords)]
        lines.append(f"**{category.upper()}** ({len(envs)}):")
        for e in envs:
            lines.append(f"  • {e}")
    else:
        # Show all categories with counts
        for cat, keywords in categories.items():
            cat_envs = [e for e in all_envs if any(k in e for k in keywords)]
            lines.append(f"**{cat.upper()}** ({len(cat_envs)}): {', '.join(sorted(cat_envs)[:5])}...")

        lines.append(f"\n**Total registered**: {len(list(all_envs))}")

    # Custom envs
    custom_files = list(RL_CUSTOM_ENVS_DIR.glob("*.py")) if RL_CUSTOM_ENVS_DIR.exists() else []
    if custom_files or _custom_envs:
        lines.append(f"\n**CUSTOM** ({max(len(custom_files), len(_custom_envs))}):")
        names = set(list(_custom_envs.keys()) + [f.stem for f in custom_files])
        for name in sorted(names):
            loaded = "✅" if name in _custom_envs else "💾"
            lines.append(f"  {loaded} custom:{name}")

    return {"status": "success", "content": [{"text": "\n".join(lines)}]}


def _action_list_models() -> Dict[str, Any]:
    """List saved RL models."""
    if not RL_MODELS_DIR.exists():
        return {"status": "success", "content": [{"text": "No saved models yet. Train one first!"}]}

    lines = ["📦 Saved RL Models:\n"]

    for model_dir in sorted(RL_MODELS_DIR.iterdir()):
        if not model_dir.is_dir():
            continue

        # Check for model files
        final = model_dir / "final_model.zip"
        best = model_dir / "best" / "best_model.zip"

        size_mb = 0
        if final.exists():
            size_mb = final.stat().st_size / (1024 * 1024)
        elif best.exists():
            size_mb = best.stat().st_size / (1024 * 1024)

        has_final = "✅" if final.exists() else "❌"
        has_best = "✅" if best.exists() else "❌"

        lines.append(f"  📁 **{model_dir.name}** ({size_mb:.1f} MB)")
        lines.append(f"     Final: {has_final} | Best: {has_best}")
        lines.append(f"     Path: {model_dir}")

    return {"status": "success", "content": [{"text": "\n".join(lines)}]}


def _action_sweep(
    env_id: str,
    algorithm: str = "PPO",
    n_trials: int = 5,
    total_timesteps: int = 50000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Simple hyperparameter sweep — tries different configs and picks the best."""
    import numpy as np

    # Define search space per algorithm
    search_spaces = {
        "PPO": [
            {"learning_rate": 3e-4, "n_steps": 2048, "batch_size": 64, "n_epochs": 10, "gamma": 0.99},
            {"learning_rate": 1e-3, "n_steps": 1024, "batch_size": 32, "n_epochs": 5, "gamma": 0.99},
            {"learning_rate": 1e-4, "n_steps": 4096, "batch_size": 128, "n_epochs": 20, "gamma": 0.999},
            {"learning_rate": 5e-4, "n_steps": 512, "batch_size": 64, "n_epochs": 10, "gamma": 0.98},
            {"learning_rate": 3e-4, "n_steps": 2048, "batch_size": 256, "n_epochs": 10, "gamma": 0.995},
            {"learning_rate": 7e-4, "n_steps": 1024, "batch_size": 64, "n_epochs": 15, "gamma": 0.99},
            {"learning_rate": 2e-4, "n_steps": 2048, "batch_size": 64, "n_epochs": 10, "gamma": 0.999, "ent_coef": 0.01},
            {"learning_rate": 5e-4, "n_steps": 2048, "batch_size": 128, "n_epochs": 5, "gamma": 0.99, "clip_range": 0.1},
        ],
        "A2C": [
            {"learning_rate": 7e-4, "n_steps": 5, "gamma": 0.99},
            {"learning_rate": 1e-3, "n_steps": 8, "gamma": 0.995},
            {"learning_rate": 3e-4, "n_steps": 16, "gamma": 0.99},
            {"learning_rate": 5e-4, "n_steps": 5, "gamma": 0.999},
            {"learning_rate": 1e-4, "n_steps": 32, "gamma": 0.99},
        ],
        "DQN": [
            {"learning_rate": 1e-3, "buffer_size": 100000, "batch_size": 32, "gamma": 0.99},
            {"learning_rate": 5e-4, "buffer_size": 50000, "batch_size": 64, "gamma": 0.99},
            {"learning_rate": 1e-4, "buffer_size": 200000, "batch_size": 128, "gamma": 0.999},
            {"learning_rate": 3e-4, "buffer_size": 100000, "batch_size": 32, "gamma": 0.98},
            {"learning_rate": 5e-4, "buffer_size": 100000, "batch_size": 64, "gamma": 0.99, "exploration_fraction": 0.2},
        ],
        "SAC": [
            {"learning_rate": 3e-4, "buffer_size": 100000, "batch_size": 256, "gamma": 0.99},
            {"learning_rate": 1e-3, "buffer_size": 50000, "batch_size": 128, "gamma": 0.99},
            {"learning_rate": 1e-4, "buffer_size": 300000, "batch_size": 256, "gamma": 0.999},
            {"learning_rate": 5e-4, "buffer_size": 100000, "batch_size": 64, "gamma": 0.98},
            {"learning_rate": 3e-4, "buffer_size": 200000, "batch_size": 256, "gamma": 0.99, "tau": 0.01},
        ],
    }

    configs = search_spaces.get(algorithm.upper(), search_spaces["PPO"])[:n_trials]

    # Pad with random variations if n_trials > available configs
    while len(configs) < n_trials:
        base = configs[np.random.randint(0, len(configs))]
        variant = {k: v * np.random.uniform(0.5, 2.0) if isinstance(v, float) else v for k, v in base.items()}
        configs.append(variant)

    print(f"\n🔍 Hyperparameter sweep: {algorithm} on {env_id}")
    print(f"   Trials: {n_trials} | Steps per trial: {total_timesteps:,}\n")

    results = []
    for i, hp in enumerate(configs):
        print(f"\n--- Trial {i + 1}/{n_trials} ---")
        print(f"   Config: {json.dumps({k: round(v, 6) if isinstance(v, float) else v for k, v in hp.items()})}")

        try:
            result = _action_train(
                env_id=env_id,
                algorithm=algorithm,
                total_timesteps=total_timesteps,
                seed=seed + i * 100,
                hyperparams=hp,
                save_name=f"sweep_{env_id.replace('/', '_')}_{algorithm}_trial{i}",
            )

            # Extract reward from result
            json_data = None
            for content in result.get("content", []):
                if "json" in content:
                    json_data = content["json"]
                    break

            mean_reward = json_data.get("best_mean_reward", 0) if json_data else 0
            results.append({"trial": i, "config": hp, "mean_reward": mean_reward, "model_path": json_data.get("best_model_path", "") if json_data else ""})
            print(f"   → Mean reward: {mean_reward:.2f}")

        except Exception as e:
            print(f"   → Failed: {e}")
            results.append({"trial": i, "config": hp, "mean_reward": -float("inf"), "error": str(e)})

    # Find best
    best = max(results, key=lambda x: x["mean_reward"])

    lines = [
        f"\n🏆 Sweep Complete!\n",
        f"   Best trial: #{best['trial']} with mean reward {best['mean_reward']:.2f}",
        f"   Best config: {json.dumps({k: round(v, 6) if isinstance(v, float) else v for k, v in best['config'].items()}, indent=4)}",
        f"   Best model: {best.get('model_path', 'N/A')}",
        f"\n   All results:",
    ]
    for r in sorted(results, key=lambda x: x["mean_reward"], reverse=True):
        status = "🏆" if r["trial"] == best["trial"] else "  "
        lines.append(f"   {status} Trial {r['trial']}: reward={r['mean_reward']:.2f}")

    return {
        "status": "success",
        "content": [
            {"text": "\n".join(lines)},
            {"json": {"best_trial": best, "all_results": results}},
        ],
    }


def _action_continue_training(
    model_path: str,
    env_id: str = None,
    algorithm: str = None,
    additional_timesteps: int = 100000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Continue training a saved model for more timesteps."""

    if algorithm is None:
        for algo_name in ALGORITHMS:
            if algo_name in str(model_path).upper():
                algorithm = algo_name
                break
        if algorithm is None:
            algorithm = "PPO"

    if env_id is None:
        model_dir = Path(model_path).parent
        for part in [model_dir.name, model_dir.parent.name]:
            for algo_name in ALGORITHMS:
                if part.endswith(f"_{algo_name}"):
                    env_id = part[: -(len(algo_name) + 1)]
                    break
            if env_id:
                break

    if env_id is None:
        return {
            "status": "error",
            "content": [{"text": "❌ Could not auto-detect env_id. Please specify it."}],
        }

    from stable_baselines3.common.vec_env import DummyVecEnv
    from stable_baselines3.common.monitor import Monitor

    algo_cls = _get_algorithm_class(algorithm)
    env = DummyVecEnv([lambda: Monitor(_make_env(env_id, seed=seed))])

    print(f"\n🔄 Continuing training: {algorithm} on {env_id}")
    print(f"   Loading: {model_path}")
    print(f"   Additional steps: {additional_timesteps:,}\n")

    model = algo_cls.load(model_path, env=env)

    progress = _ProgressCallback(additional_timesteps)
    start_time = time.time()

    model.learn(
        total_timesteps=additional_timesteps,
        callback=[progress.get()],
        reset_num_timesteps=False,
    )

    # Save back
    model.save(model_path)
    elapsed = time.time() - start_time

    env.close()

    return {
        "status": "success",
        "content": [{"text": f"✅ Continued training for {additional_timesteps:,} more steps ({elapsed:.1f}s). Model saved to {model_path}"}],
    }


def _action_compare(
    model_paths: List[str],
    env_id: str,
    n_episodes: int = 20,
    seed: int = 42,
) -> Dict[str, Any]:
    """Compare multiple trained models on the same environment."""
    import numpy as np

    results = []

    for path in model_paths:
        # Detect algorithm
        algorithm = "PPO"
        for algo_name in ALGORITHMS:
            if algo_name in str(path).upper():
                algorithm = algo_name
                break

        print(f"\n📊 Evaluating: {Path(path).parent.name} ({algorithm})")

        eval_result = _action_eval(
            model_path=path,
            env_id=env_id,
            algorithm=algorithm,
            n_episodes=n_episodes,
            seed=seed,
        )

        json_data = None
        for content in eval_result.get("content", []):
            if "json" in content:
                json_data = content["json"]
                break

        results.append({
            "path": path,
            "name": Path(path).parent.name,
            "algorithm": algorithm,
            **(json_data or {"mean_reward": 0, "std_reward": 0}),
        })

    # Sort by mean reward
    results.sort(key=lambda x: x["mean_reward"], reverse=True)

    lines = [f"\n🏆 Model Comparison on {env_id} ({n_episodes} episodes each):\n"]
    for i, r in enumerate(results):
        medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "  "
        lines.append(
            f"  {medal} {r['name']} ({r['algorithm']}): "
            f"{r['mean_reward']:.2f} ± {r.get('std_reward', 0):.2f}"
        )

    return {
        "status": "success",
        "content": [
            {"text": "\n".join(lines)},
            {"json": {"rankings": results}},
        ],
    }


# ─── Helper ──────────────────────────────────────────────────────────────────

def _indent(code: str, spaces: int) -> str:
    """Indent code block by N spaces."""
    prefix = " " * spaces
    return "\n".join(prefix + line for line in code.strip().split("\n"))


# ─── Main Tool Entry Point ──────────────────────────────────────────────────

@tool
def rl(
    action: str,
    env_id: str = None,
    algorithm: str = "PPO",
    total_timesteps: int = 100000,
    seed: int = 42,
    hyperparams: str = None,
    save_name: str = None,
    n_envs: int = 1,
    eval_freq: int = 10000,
    device: str = "auto",
    model_path: str = None,
    n_episodes: int = 20,
    deterministic: bool = True,
    render: bool = False,
    record_video: bool = False,
    video_path: str = None,
    env_name: str = None,
    reward_code: str = None,
    obs_dim: int = 4,
    act_dim: int = 1,
    act_type: str = "continuous",
    max_steps: int = 1000,
    description: str = "",
    reset_code: str = None,
    step_code: str = None,
    category: str = None,
    n_trials: int = 5,
    additional_timesteps: int = 100000,
    model_paths: str = None,
) -> Dict[str, Any]:
    """
    🎮 Reinforcement Learning toolkit for DevDuck.

    Train, evaluate, and deploy RL agents using Stable-Baselines3 + Gymnasium.
    Create custom environments from reward functions. Learn ANYTHING.

    Actions:
        train         - Train an RL agent (PPO, A2C, DQN, SAC, TD3, DDPG)
        eval          - Evaluate a trained model
        play          - Watch a trained agent play (render or record video)
        create_env    - Create a custom Gymnasium env from Python code
        list_envs     - List available environments (built-in + custom)
        list_models   - List saved RL models
        sweep         - Hyperparameter sweep (tries N configs, picks best)
        continue      - Continue training a saved model for more steps
        compare       - Compare multiple models on the same environment

    Args:
        action: One of the actions above
        env_id: Gymnasium env ID (e.g., "CartPole-v1") or "custom:name"
        algorithm: RL algorithm — PPO, A2C, DQN, SAC, TD3, DDPG
        total_timesteps: Training budget
        seed: Random seed
        hyperparams: JSON string of hyperparameters
        save_name: Custom name for saved model
        n_envs: Number of parallel training environments
        eval_freq: Evaluate every N timesteps
        device: "auto", "cpu", "cuda", "mps"
        model_path: Path to a saved model (for eval/play/continue)
        n_episodes: Number of episodes for eval/play
        deterministic: Use deterministic actions for eval
        render: Render environment during play
        record_video: Record video during play
        video_path: Custom video save path
        env_name: Name for custom environment
        reward_code: Python code for reward function
        obs_dim: Observation space dimension (custom env)
        act_dim: Action space dimension (custom env)
        act_type: "continuous" or "discrete" (custom env)
        max_steps: Max steps per episode (custom env)
        description: Description for custom env
        reset_code: Custom reset code (advanced custom env)
        step_code: Custom step code (advanced custom env)
        category: Filter for list_envs (classic, box2d, mujoco, atari)
        n_trials: Number of trials for sweep
        additional_timesteps: Extra steps for continue action
        model_paths: Comma-separated model paths for compare

    Examples:
        # Train CartPole
        rl(action="train", env_id="CartPole-v1", algorithm="PPO", total_timesteps=50000)

        # Create a custom balancing environment
        rl(action="create_env", env_name="balance",
           reward_code="def reward(state, action):\\n    angle = state[0]\\n    return state, -abs(angle), abs(angle) > 1.0",
           obs_dim=4, act_dim=1)

        # Train on custom env
        rl(action="train", env_id="custom:balance", algorithm="SAC")

        # Evaluate
        rl(action="eval", model_path="rl_models/CartPole-v1_PPO/best/best_model")

        # Hyperparameter sweep
        rl(action="sweep", env_id="LunarLander-v3", n_trials=8)
    """
    try:
        # Parse hyperparams from JSON string if provided
        hp = json.loads(hyperparams) if hyperparams else None

        if action == "train":
            if not env_id:
                return {"status": "error", "content": [{"text": "❌ env_id required for training"}]}
            return _action_train(
                env_id=env_id, algorithm=algorithm, total_timesteps=total_timesteps,
                seed=seed, hyperparams=hp, save_name=save_name, n_envs=n_envs,
                eval_freq=eval_freq, device=device,
            )

        elif action == "eval":
            if not model_path:
                return {"status": "error", "content": [{"text": "❌ model_path required for evaluation"}]}
            return _action_eval(
                model_path=model_path, env_id=env_id, algorithm=algorithm,
                n_episodes=n_episodes, deterministic=deterministic, seed=seed, render=render,
            )

        elif action == "play":
            if not model_path:
                return {"status": "error", "content": [{"text": "❌ model_path required for play"}]}
            return _action_play(
                model_path=model_path, env_id=env_id, algorithm=algorithm,
                n_episodes=n_episodes, seed=seed, record_video=record_video, video_path=video_path,
            )

        elif action == "create_env":
            if not env_name:
                return {"status": "error", "content": [{"text": "❌ env_name required"}]}
            if not reward_code and not (step_code and reset_code):
                return {"status": "error", "content": [{"text": "❌ Either reward_code OR (step_code + reset_code) required"}]}
            return _action_create_env(
                env_name=env_name, reward_code=reward_code or "", obs_dim=obs_dim,
                act_dim=act_dim, act_type=act_type, max_steps=max_steps,
                description=description, reset_code=reset_code, step_code=step_code,
            )

        elif action == "list_envs":
            return _action_list_envs(category=category)

        elif action == "list_models":
            return _action_list_models()

        elif action == "sweep":
            if not env_id:
                return {"status": "error", "content": [{"text": "❌ env_id required for sweep"}]}
            return _action_sweep(
                env_id=env_id, algorithm=algorithm, n_trials=n_trials,
                total_timesteps=total_timesteps, seed=seed,
            )

        elif action == "continue":
            if not model_path:
                return {"status": "error", "content": [{"text": "❌ model_path required for continue"}]}
            return _action_continue_training(
                model_path=model_path, env_id=env_id, algorithm=algorithm,
                additional_timesteps=additional_timesteps, seed=seed,
            )

        elif action == "compare":
            if not model_paths:
                return {"status": "error", "content": [{"text": "❌ model_paths required (comma-separated)"}]}
            if not env_id:
                return {"status": "error", "content": [{"text": "❌ env_id required for compare"}]}
            paths = [p.strip() for p in model_paths.split(",")]
            return _action_compare(model_paths=paths, env_id=env_id, n_episodes=n_episodes, seed=seed)

        else:
            return {
                "status": "error",
                "content": [{"text": f"❌ Unknown action: {action}. Available: train, eval, play, create_env, list_envs, list_models, sweep, continue, compare"}],
            }

    except Exception as e:
        return {
            "status": "error",
            "content": [{"text": f"❌ RL Error:\n{traceback.format_exc()}"}],
        }
