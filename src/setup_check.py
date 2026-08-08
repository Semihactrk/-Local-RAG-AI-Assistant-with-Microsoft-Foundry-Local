"""
This script:
  1. Initializes the Foundry Local SDK.
  2. Discovers available execution providers (EPs) and downloads/registers
     the hardware-accelerated ones (CUDA/DirectML/NPU etc.). Skipping this
     step means Foundry Local silently falls back to CPU -- visually verify
     in the table below that the GPU is actually registered.
  3. Runs an end-to-end "Hello Model" test by downloading and loading a
     small model (qwen2.5-0.5b).

Run:
    .venv\\Scripts\\python.exe src\\setup_check.py
"""

import sys

from foundry_local_sdk import Configuration, FoundryLocalManager

sys.stdout.reconfigure(encoding="utf-8")  # avoid mangled characters on Windows consoles


def main():
    config = Configuration(app_name="foundry_rag_demo")
    FoundryLocalManager.initialize(config)
    manager = FoundryLocalManager.instance

    # --- 1. List execution providers BEFORE registration ---
    eps_before = manager.discover_eps()
    print("Execution providers before registration:")
    print(f"  {'Name':<30}  Registered?")
    print(f"  {'-' * 30}  ----------")
    for ep in eps_before:
        print(f"  {ep.name:<30}  {ep.is_registered}")

    # --- 2. Download + register hardware-accelerated EPs ---
    current_ep = ""

    def ep_progress(ep_name: str, percent: float):
        nonlocal current_ep
        if ep_name != current_ep:
            if current_ep:
                print()
            current_ep = ep_name
        print(f"\r  {ep_name:<30}  {percent:5.1f}%", end="", flush=True)

    print("\nDownloading / registering hardware-accelerated EPs...")
    manager.download_and_register_eps(progress_callback=ep_progress)
    if current_ep:
        print()

    # --- 3. Show status AFTER registration ---
    eps_after = manager.discover_eps()
    print("\nExecution provider status after registration:")
    print(f"  {'Name':<30}  Registered?")
    print(f"  {'-' * 30}  ----------")
    gpu_registered = False
    for ep in eps_after:
        print(f"  {ep.name:<30}  {ep.is_registered}")
        name_lower = ep.name.lower()
        if ep.is_registered and any(x in name_lower for x in ("cuda", "dml", "directml", "nv", "gpu")):
            gpu_registered = True

    if gpu_registered:
        print("\n[OK] A GPU-accelerated execution provider appears to be REGISTERED.")
    else:
        print(
            "\n[WARNING] No GPU execution provider shows as 'registered'. "
            "The system will likely fall back to CPU. Check your NVIDIA "
            "drivers and whether the CUDA EP package actually downloaded."
        )

    # --- 4. End-to-end test with a small model ---
    print("\n--- Hello Model test (qwen2.5-0.5b) ---")
    model = manager.catalog.get_model("qwen2.5-0.5b")
    model.download(
        lambda progress: print(f"\rDownloading model: {progress:.2f}%", end="", flush=True)
    )
    print()
    model.load()
    print(f"Model loaded: {model.id}")
    print(f"  -> Compare which EP/hardware this model is running on against the table above.")

    client = model.get_chat_client()
    messages = [{"role": "user", "content": "Hi, introduce yourself in one short sentence."}]

    print("\nAssistant: ", end="", flush=True)
    for chunk in client.complete_streaming_chat(messages):
        if not chunk.choices:
            continue
        content = chunk.choices[0].delta.content
        if content:
            print(content, end="", flush=True)
    print()

    model.unload()
    print("\nModel unloaded. Setup check complete.")


if __name__ == "__main__":
    main()
