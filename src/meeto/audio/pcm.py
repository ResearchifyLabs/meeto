"""PCM conversion helpers."""

from array import array
from collections.abc import Iterable


def downsample_float32(samples: Iterable[float], in_rate: int, out_rate: int) -> list[float]:
    if in_rate <= 0 or out_rate <= 0:
        raise ValueError("Sample rates must be positive.")
    if out_rate > in_rate:
        raise ValueError("Downsample target must be <= input rate.")

    if in_rate == out_rate:
        return list(samples)

    samples_list = list(samples)
    ratio = in_rate / out_rate
    output_len = int(len(samples_list) / ratio)
    if output_len <= 0:
        return []

    output = []
    for i in range(output_len):
        start = int(i * ratio)
        end = int((i + 1) * ratio)
        if end <= start:
            end = start + 1
        window = samples_list[start:end]
        output.append(sum(window) / len(window))
    return output


def float32_to_pcm16(samples: Iterable[float]) -> bytes:
    pcm = array("h")
    for sample in samples:
        if sample > 1.0:
            sample = 1.0
        elif sample < -1.0:
            sample = -1.0
        if sample < 0:
            pcm.append(int(sample * 32768))
        else:
            pcm.append(int(sample * 32767))
    return pcm.tobytes()
