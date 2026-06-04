"""Pull Docker images required for a mixed task list.

Dispatches on task_id prefix:

* ``user:...`` (cybergym binary-exploit tasks): pull one image per selected
  mode from ``TaskMetadata.images[mode]``. Defaults to ``exp.none``.
* ``kernel:...`` (kernelctf + syzbot): pull ``KernelTaskMetadata.image_name``.
* ``v8:...``: pull one image per selected variant. ``main`` →
  ``V8TaskMetadata.image`` (default), ``nosandbox`` →
  ``V8TaskMetadata.image_no_sandbox`` (skipped with a warning for tasks
  that don't define one, e.g. sandbox-escape tasks), ``nodefense`` →
  prefer ``image_no_sandbox`` if available, else fall back to ``image``
  (never skips a task that has any image).

Both the hashed (``user:<hex>``) and alias (``user:cybergym/arvo_1234``)
forms are accepted — the metadata loaders index both.

Usage::

    # Only exp.none mode for user tasks, default image for others
    python scripts/setup/pull_images.py data/task_ids/ready.txt

    # Several cybergym variants at once
    python scripts/setup/pull_images.py data/task_ids/ready.txt \\
        --user-modes exp.none exp.canary exp.pie

    # Pull both main and no-sandbox v8 images alongside the default user/kernel
    python scripts/setup/pull_images.py data/task_ids/smallset.txt \\
        --v8-variants main nosandbox

    # One image per v8 task, preferring nosandbox where available
    python scripts/setup/pull_images.py data/task_ids/smallset.txt \\
        --v8-variants nodefense

    # Mixed list (works transparently)
    python scripts/setup/pull_images.py data/task_ids/smallset.txt --workers 16
"""

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm

import docker
from cybergym.task.metadata import (
    KERNEL_TASK_METADATA,
    TASK_METADATA,
    V8_TASK_METADATA,
)


def pull_image(client, image_name: str) -> str:
    client.images.pull(image_name)
    return image_name


V8_VARIANTS = {"main", "nosandbox", "nodefense"}


def images_for_task(
    task_id: str,
    modes: list[str],
    v8_variants: list[str],
) -> list[str]:
    """Resolve the list of images to pull for a single task_id.

    Missing task IDs or missing user-mode / v8-variant entries trigger a
    warning and are skipped (function returns what it could resolve).
    """
    if task_id.startswith("user:"):
        meta = TASK_METADATA.get(task_id)
        if meta is None:
            print(f"[warn] user task not in metadata: {task_id}", file=sys.stderr)
            return []
        images = []
        for mode in modes:
            img = meta.images.get(mode)
            if img is None:
                print(
                    f"[warn] mode {mode!r} not available for {task_id}",
                    file=sys.stderr,
                )
                continue
            images.append(img)
        return images

    if task_id.startswith("kernel:"):
        meta = KERNEL_TASK_METADATA.get(task_id)
        if meta is None:
            print(f"[warn] kernel task not in metadata: {task_id}", file=sys.stderr)
            return []
        return [meta.image_name]

    if task_id.startswith("v8:"):
        meta = V8_TASK_METADATA.get(task_id)
        if meta is None:
            print(f"[warn] v8 task not in metadata: {task_id}", file=sys.stderr)
            return []
        images = []
        for variant in v8_variants:
            if variant == "main":
                if meta.image is None:
                    print(
                        f"[warn] v8 task {task_id} has no main image "
                        f"(predates sandbox); skipping",
                        file=sys.stderr,
                    )
                    continue
                images.append(meta.image)
            elif variant == "nosandbox":
                if meta.image_no_sandbox is None:
                    print(
                        f"[warn] v8 task {task_id} has no nosandbox variant; skipping",
                        file=sys.stderr,
                    )
                    continue
                images.append(meta.image_no_sandbox)
            elif variant == "nodefense":
                # Prefer nosandbox, fall back to main; never both.
                if meta.image_no_sandbox is not None:
                    images.append(meta.image_no_sandbox)
                elif meta.image is not None:
                    images.append(meta.image)
                else:
                    print(
                        f"[warn] v8 task {task_id} has neither main nor "
                        f"nosandbox image; skipping",
                        file=sys.stderr,
                    )
            else:
                print(f"[warn] unknown v8 variant {variant!r}", file=sys.stderr)
        return images

    print(f"[warn] unrecognised task_id prefix: {task_id}", file=sys.stderr)
    return []


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pull Docker images for a mixed task list.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("task_ids_file", help="Text file with one task ID per line.")
    parser.add_argument(
        "--user-modes",
        nargs="+",
        default=["exp.none"],
        help="Image modes to pull for user/cybergym tasks. Ignored for kernel/v8.",
    )
    parser.add_argument(
        "--v8-variants",
        nargs="+",
        choices=sorted(V8_VARIANTS),
        default=["main"],
        help=(
            "V8 image variants to pull. "
            "'main' uses TaskMetadata.image (skipped for pre-sandbox tasks); "
            "'nosandbox' uses TaskMetadata.image_no_sandbox (skipped for "
            "sandbox-escape tasks); "
            "'nodefense' picks nosandbox if available, else main — never "
            "skips a task that has any image. "
            "Ignored for user/kernel."
        ),
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Number of parallel pull workers.",
    )
    parser.add_argument(
        "--skip-local",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Skip images already present locally without hitting the registry. "
            "Avoids consuming Docker Hub rate-limit budget on re-runs. "
            "On by default; pass --no-skip-local to force `docker pull` for "
            "every image (validates manifests / refreshes already-pulled tags)."
        ),
    )
    args = parser.parse_args()

    with open(args.task_ids_file) as f:
        task_ids = [line.strip() for line in f if line.strip()]

    # Deduplicate: many kernel tasks share the same image.
    seen: set[str] = set()
    for task_id in task_ids:
        for img in images_for_task(task_id, args.user_modes, args.v8_variants):
            if img not in seen:
                seen.add(img)

    images = list(sorted(seen))

    if not images:
        print("No images resolved; nothing to pull.", file=sys.stderr)
        return 1

    client = docker.from_env()

    if args.skip_local:
        local = {tag for img in client.images.list() for tag in img.tags}
        before = len(images)
        images = [img for img in images if img not in local]
        skipped = before - len(images)
        if skipped:
            print(f"Skipping {skipped} image(s) already present locally.")

    if not images:
        print("All resolved images are already present locally; nothing to pull.")
        return 0

    print(f"Pulling {len(images)} unique images ({args.workers} workers)")
    failures: list[tuple[str, str]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(pull_image, client, img): img for img in images}
        with tqdm(total=len(futures), unit="image") as pbar:
            for future in as_completed(futures):
                image_name = futures[future]
                try:
                    future.result()
                    pbar.set_postfix_str(image_name.split("/")[-1])
                except Exception as e:
                    failures.append((image_name, str(e)))
                    tqdm.write(f"Failed to pull {image_name}: {e}")
                pbar.update(1)

    if failures:
        print(f"\n{len(failures)} image(s) failed to pull:", file=sys.stderr)
        for img, err in failures:
            print(f"  {img}: {err}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
