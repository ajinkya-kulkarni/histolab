# encoding: utf-8

# ------------------------------------------------------------------------
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# ------------------------------------------------------------------------

"""Provides the Slide class.

Slide is the main API class for manipulating WSI slides images.
"""

import math
import os
import pathlib
from typing import Tuple, Union

import matplotlib.pyplot as plt
import ntpath
import numpy as np
import openslide
import PIL

from .util import Time

IMG_EXT = "png"
THUMBNAIL_SIZE = 300


class Slide(object):
    """Provides Slide objects and expose property and methods.

    HERE-> expand the docstring
    """

    def __init__(self, path: str, processed_path: str) -> None:
        self._path = path
        self._processed_path = processed_path

    # ---public interface methods and properties---

    def resampled_array(self, scale_factor=32) -> np.array:
        return self._resample(scale_factor)[1]

    def save_scaled_image(self, scale_factor=32) -> None:
        """Save a scaled image in the correct path
        
        Parameters
        ----------
        scale_factor : int, default is 32
            Image scaling factor
        
        """
        os.makedirs(self._processed_path, exist_ok=True)
        img = self._resample(scale_factor)[0]
        img.save(self.scaled_image_path(scale_factor))

    def save_thumbnail(self) -> None:
        """Save a thumbnail in the correct path"""
        os.makedirs(self._processed_path, exist_ok=True)

        img = self._wsi.get_thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE))

        folder = os.path.dirname(self.thumbnail_path)
        pathlib.Path(folder).mkdir(exist_ok=True)
        img.save(self.thumbnail_path)

    def scaled_image_path(self, scale_factor=32) -> str:
        """Returns slide image path.

        Parameters
        ----------
        scale_factor : int, default is 32
            Image scaling factor

        Returns
        -------
        img_path : str
        
        """
        img_path = self._breadcumb(self._processed_path, scale_factor)
        return img_path

    @property
    def thumbnail_path(self) -> str:
        """Returns thumbnail image path.

        Returns
        -------
        thumb_path : str
        """
        thumb_path = os.path.join(
            self._processed_path, "thumbnails", f"{self.name}.{IMG_EXT}"
        )

        return thumb_path

    @property
    def dimensions(self) -> Tuple[int, int]:
        """Returns the slide dimensions (w,h)

        Returns
        -------
        dimensions : tuple (width, height)
        """
        return self._wsi.dimensions

    @property
    def name(self) -> str:
        """Retrieves the slide name without extension.

        Returns
        -------
        name : str
        """
        return ntpath.basename(self._path).split(".")[0]

    # ---private interface methods and properties---

    def _breadcumb(self, directory_path, scale_factor=32) -> str:
        """Returns a complete path according to the give directory path

        Parameters
        ----------
        directory_path: str
        scale_factor : int, default is 32
            Image scaling factor

        Returns
        -------
        final_path: str, a real and complete path starting from the dir path
                    e.g. /processed_path/my-image-name-x32/
                         /thumb_path/my-image-name-x32/thumbs
        """
        large_w, large_h, new_w, new_h = self._resampled_dimensions(scale_factor)
        if {large_w, large_h, new_w, new_h} == {None}:
            final_path = os.path.join(directory_path, f"{self.name}*.{IMG_EXT}")
        else:
            final_path = os.path.join(
                directory_path,
                f"{self.name}-{scale_factor}x-{large_w}x{large_h}-{new_w}x"
                f"{new_h}.{IMG_EXT}",
            )
        return final_path

    def _resample(self, scale_factor=32) -> Tuple[PIL.Image.Image, np.array]:
        """Converts a slide to a scaled-down PIL image.

        The PIL image is also converted to array.
        image is the scaled-down PIL image, original width and original height
        are the width and height of the WSI, new width and new height are the
        dimensions of the PIL image.

        Parameters
        ----------
        scale_factor : int, default is 32
            Image scaling factor

        Returns
        -------
        img, arr_img, large_w, large_h, new_w, new_h: tuple
        """
        # TODO: use logger instead of print(f"Opening Slide {slide_filepath}")

        large_w, large_h, new_w, new_h = self._resampled_dimensions(scale_factor)
        level = self._wsi.get_best_level_for_downsample(scale_factor)
        whole_slide_image = self._wsi.read_region(
            (0, 0), level, self._wsi.level_dimensions[level]
        )
        # ---converts openslide read_region to an actual RGBA image---
        whole_slide_image = whole_slide_image.convert("RGB")
        img = whole_slide_image.resize((new_w, new_h), PIL.Image.BILINEAR)
        arr_img = np.asarray(img)
        return img, arr_img

    def _resampled_dimensions(self, scale_factor=32) -> Tuple[int, int, int, int]:
        large_w, large_h = self.dimensions
        new_w = math.floor(large_w / scale_factor)
        new_h = math.floor(large_h / scale_factor)
        return large_w, large_h, new_w, new_h

    @property
    def _wsi(self) -> Union[openslide.OpenSlide, openslide.ImageSlide]:
        """Open the slide and returns an openslide object

        Returns
        -------
        slide : OpenSlide object
                An OpenSlide object representing a whole-slide image.
        """
        try:
            slide = openslide.open_slide(self._path)
        except openslide.OpenSlideError:
            raise openslide.OpenSlideError(
                "Your wsi has something broken inside, a doctor is needed"
            )
        except FileNotFoundError:
            raise FileNotFoundError("The wsi path resource doesn't exist")
        return slide

    @property
    def _extension(self) -> str:
        return os.path.splitext(self._path)[1]


class SlideSet(object):
    def __init__(self, slides_path, processed_path, valid_wsi_extensions):
        self._slides_path = slides_path
        self._processed_path = processed_path
        self._valid_wsi_extensions = valid_wsi_extensions

    def save_rescaled_slides(self, n=0):
        """Save rescaled images

        Parameters
        ----------
        n: int
           first n slides in dataset folder to rescale and save
        """
        # TODO: add logger if n>total_slide and log saved images names
        os.makedirs(self._processed_path, exist_ok=True)
        n = self.total_slides if (n > self.total_slides or n == 0) else n

        for slide in self.slides[:n]:
            slide.save_scaled_image()

    def save_thumbnails(self, scale_factor=32, n=0):
        """Save thumbnails

        Parameters
        ----------
        n: int
            first n slides in dataset folder
        scale_factor : int, default is 32
            Image scaling factor
            
        """
        # TODO: add logger n>total_slide and log thumbnails names
        os.makedirs(self._processed_path, exist_ok=True)
        n = self.total_slides if (n > self.total_slides or n == 0) else n
        for slide in self.slides[:n]:
            slide.save_thumbnail(scale_factor)

    @property
    def slides(self):
        return [
            Slide(os.path.join(self._slides_path, wsi_path), self._processed_path)
            for wsi_path in os.listdir(self._slides_path)
            if os.path.splitext(wsi_path)[1] in self._valid_wsi_extensions
        ]

    @property
    def slides_dimensions(self):
        return [
            {
                "wsi": slide.name,
                "width": slide.dimensions[0],
                "height": slide.dimensions[1],
                "size": slide.dimensions[0] * slide.dimensions[1],
            }
            for slide in self.slides
        ]

    @property
    def slides_stats(self):
        """Retrieve statistic/graphs of wsi files contained in the dataset"""
        t = Time()

        basic_stats = {
            "no_of_slides": self.total_slides,
            "max_width": self._max_width_slide,
            "max_height": self._max_height_slide,
            "max_size": self._max_size_slide,
            "min_width": self._min_width_slide,
            "min_height": self._min_height_slide,
            "min_size": self._min_size_slide,
            "avg_width": self._avg_width_slide,
            "avg_height": self._avg_height_slide,
            "avg_size": self._avg_size_slide,
        }

        t.elapsed_display()

        x, y = zip(*[slide.dimensions for slide in self.slides])
        colors = np.random.rand(self.total_slides)
        sizes = 8 * self.total_slides

        plt.ioff()

        fig, ax = plt.subplots()
        ax.scatter(x, y, s=sizes, c=colors, alpha=0.7)
        plt.xlabel("width (pixels)")
        plt.ylabel("height (pixels)")
        plt.title("WSI sizes")
        plt.set_cmap("prism")

        # plt.scatter(x, y, s=sizes, c=colors, alpha=0.7)
        # plt.xlabel("width (pixels)")
        # plt.ylabel("height (pixels)")
        # plt.title("SVS Image Sizes (Labeled with slide numbers)")
        # plt.set_cmap("prism")
        # for i in range(num_images):
        #     snum = i + 1
        #     plt.annotate(str(snum), (x[i], y[i]))
        # plt.tight_layout()

        # area = [w * h / 1e6 for (w, h) in slide_stats]
        # plt.hist(area, bins=64)
        # plt.xlabel("width x height (M of pixels)")
        # plt.ylabel("# images")
        # plt.title("Distribution of image sizes in millions of pixels")
        # plt.tight_layout()

        # whratio = [w / h for (w, h) in slide_stats]
        # plt.hist(whratio, bins=64)
        # plt.xlabel("width to height ratio")
        # plt.ylabel("# images")
        # plt.title("Image shapes (width to height)")
        # plt.tight_layout()

        # hwratio = [h / w for (w, h) in slide_stats]
        # plt.hist(hwratio, bins=64)
        # plt.xlabel("height to width ratio")
        # plt.ylabel("# images")
        # plt.title("Image shapes (height to width)")
        # plt.tight_layout()
        # t.elapsed_display()
        return basic_stats, fig

    @property
    def total_slides(self):
        return len(self.slides)

    @property
    def _avg_width_slide(self):
        return sum(d["width"] for d in self.slides_dimensions) / self.total_slides

    @property
    def _avg_height_slide(self):
        return sum(d["height"] for d in self.slides_dimensions) / self.total_slides

    @property
    def _avg_size_slide(self):
        return sum(d["size"] for d in self.slides_dimensions) / self.total_slides

    @property
    def _max_height_slide(self):
        max_height = max(self.slides_dimensions, key=lambda x: x["height"])
        return {"slide": max_height["wsi"], "height": max_height["height"]}

    @property
    def _max_size_slide(self):
        max_size = max(self.slides_dimensions, key=lambda x: x["size"])
        return {"slide": max_size["wsi"], "size": max_size["size"]}

    @property
    def _max_width_slide(self):
        max_width = max(self.slides_dimensions, key=lambda x: x["width"])
        return {"slide": max_width["wsi"], "width": max_width["width"]}

    @property
    def _min_width_slide(self):
        min_width = min(self.slides_dimensions, key=lambda x: x["width"])
        return {"slide": min_width["wsi"], "width": min_width["width"]}

    @property
    def _min_height_slide(self):
        min_height = min(self.slides_dimensions, key=lambda x: x["height"])
        return {"slide": min_height["wsi"], "height": min_height["height"]}

    @property
    def _min_size_slide(self):
        min_size = min(self.slides_dimensions, key=lambda x: x["size"])
        return {"slide": min_size["wsi"], "height": min_size["size"]}
