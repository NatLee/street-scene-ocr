# A small, honest benchmark

How well do the three engines read Traditional Chinese street signs, and how long do they take? This folder
answers that with 32 images whose correct text is known, a simple score and a script anyone can re-run.

Results of the run on 2026-11-04 (4 CPU cores of an AMD Ryzen 9 9950X, inside the project's Docker image):

| Engine | Photos: CER | with OpenCC s2tw | Photos: lines exactly right | Synthetic: CER | Median time per photo |
|---|---:|---:|---:|---:|---:|
| PaddleOCR 3.7 (PP-OCRv6 medium) | 15.4 % | 12.4 % | 39 / 70 | 0.5 % | 1.05 s |
| RapidOCR 3.10 (PP-OCRv6 small) | 18.4 % | 15.7 % | 37 / 70 | 0.0 % | 0.35 s |
| EasyOCR 1.7.2 (CRAFT + CRNN) | 74.5 % | 74.5 % | 8 / 70 | 14.7 % | 4.78 s |

What stands out:

- **EasyOCR misses most real signs.** It finds few of the vertical and calligraphic signs (敦美苑, 鐵道模型,
  阿岸米糕) and reads の as 0. On clean synthetic signs it does much better (14.7 %), so the gap is mostly in
  detection and in handling real-world lettering.
- **The PP-OCRv6 engines are close.** PaddleOCR's larger model reads a few more lines; RapidOCR's small
  model is about three times faster and needs no download.
- **Most PP-OCR mistakes are the right character in its Simplified form**: 贺茶堂, 鲜泡手作茶, 宾馆, 凉麵,
  富锦街. The optional OpenCC conversion fixes those and costs a few correct characters (台灣 becomes 臺灣,
  貴賢里 becomes 貴賢裡); on these photos that is a net gain of about 3 points.
- **Timing varies with machine load.** An earlier run on the same machine, while other jobs were busy, measured
  0.53 s, 2.13 s and 10.7 s; the ranking did not change.

Full tables, including every photo line side by side: [results/results.md](results/results.md). Raw numbers:
[results/results.json](results/results.json).

## The images

| Set | Images | Graded lines | Where they come from |
|---|---:|---:|---|
| `photos` | 8 | 70 | Street photos from Taiwan, CC0 on Wikimedia Commons ([sources](data/photos/README.md)). Text typed from the photos. |
| `synthetic` | 24 | 40 | Signs drawn by [`make_synthetic.py`](make_synthetic.py) with the bundled Noto font, random colours, perspective, blur, noise and JPEG compression. Labels are exact. |

The two sets test different things. The photos are the real task: night lighting, glare, wires in front of
signs, calligraphy, tiny print, vertical text, Japanese の in shop names. The synthetic signs are clean and
use one font, so they mostly test whether an engine knows the **characters**: many of them (麵, 雞, 豐, 號,
鐘, 鹽, 藝 …) look different in Simplified Chinese, which is where engines trained mostly on Simplified text
slip.

## The score

**CER, character error rate**: the number of characters you would have to insert, delete or replace to turn
the engine's reading into the right text, divided by the number of characters in the right text. Lower is
better; 0 % is perfect and 100 % is as bad as reading nothing.

The details, all in [`evaluation.py`](../src/street_scene_ocr/evaluation.py) and covered by tests:

1. Only **confident** regions count (confidence above 30 %, the service default). That is what a user sees as
   green boxes.
2. Each region goes to the labelled line whose outline contains the region's centre. Pieces of a split line are
   joined in reading direction (top to bottom for vertical signs).
3. A labelled line with nothing inside it counts as all characters missed.
4. Regions outside every labelled line are reported as **extra** but do not change the CER: photos have small
   print nobody labelled, and reading it is not a mistake. A high extra count can also mean the engine
   hallucinates text in bricks or leaves, so look at both numbers.
5. Text is compared after ignoring spaces, punctuation, letter case and full/half-width differences
   (`外送專線：` equals `外送專線:`). Simplified and Traditional forms are **not** treated as equal: 麵 and 面 are
   different characters on a Taiwanese sign.
6. **Time** is the median wall-clock time per image of the engine call alone, after one warm-up image, in the
   same Docker image the service uses, on CPU.

## What this benchmark does not tell you

- **It is small.** 70 photo lines from 8 photos. One more badly read sign moves a CER by a percentage point or
  two. Treat differences of a few points as noise.
- **The labels were made by one person** and the outlines started from one of the engines (PaddleOCR), then were
  checked and corrected. That could favour PaddleOCR's way of splitting lines; the centre-in-outline rule and
  the joining of split lines are there to limit that.
- **The synthetic signs use one font**, the same one the service uses for its labels. Real signs use hundreds.
- **Timings depend on the machine** and on what else it is doing; the runs here shared a desktop CPU with other
  jobs. Compare engines within one run, not across machines.
- **The defaults are the engines' defaults.** Each engine has knobs (detection thresholds, image size, model
  size) that could change its ranking. This measures what you get out of the box.

## Run it yourself

With the Docker image (all engines and models included):

```bash
docker compose build models
docker run --rm -v street-scene-ocr_models:/models -v "$PWD:/src" -w /src street-scene-ocr:local \
    python eval/run.py
```

Or in a local environment with the engines you want installed:

```bash
pip install -e ".[rapidocr]"
python eval/run.py --engines rapidocr
```

Other tools in this folder:

- `python eval/make_synthetic.py` re-draws the synthetic signs (deterministic for a given seed and Pillow version).
- `python eval/draw_labels.py photos /tmp/labels` draws the labels on the photos, to check or edit them.
