"""Unambiguous frame/lens association for adjacent UI carts and grouped API carts."""


# Prefer fully configured adjacent pairs; preserve the original grouped API contract.
def frame_lens_pairs(kinds, optical_frames, *, allow_lens_only=False):
    frames = [index for index, kind in enumerate(kinds) if kind == "frame"]
    lenses = [index for index, kind in enumerate(kinds) if kind == "lens"]
    if not frames and allow_lens_only:
        return []
    if len(lenses) < len(optical_frames) or len(lenses) > len(frames):
        raise ValueError(
            "Cart needs one frame for each lens; every optical frame needs exactly one lens pair. "
            "Select a frame-only purchase explicitly when no lens is required."
        )
    adjacent = [(frame, frame + 1) for frame in frames if frame + 1 in lenses]
    if len(adjacent) == len(lenses) and set(optical_frames) <= {frame for frame, _ in adjacent}:
        return adjacent
    optional_frames = [frame for frame in frames if frame not in optical_frames]
    selected_frames = sorted(list(optical_frames) + optional_frames[:len(lenses) - len(optical_frames)])
    return list(zip(selected_frames, lenses))
