"""
VoiceShield — Grad-CAM Explainability Module (Production)
=========================================================
Generates spectrogram heatmaps showing WHERE the CNN detected fake artifacts.

This is critical for:
  1. User trust — "Why did you flag this as fake?"
  2. Judge Q&A — visual proof that the model isn't a black box
  3. Forensic evidence — the heatmap can be included in the PDF report

Usage:
    from ai.gradcam import GradCAMGenerator
    gradcam = GradCAMGenerator(detector.get_cnn_for_gradcam())
    b64_png = gradcam.generate(mel_spectrogram)
"""
import torch
import torch.nn.functional as F
import numpy as np
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for server-side rendering
import matplotlib.pyplot as plt
import io
import base64
from typing import Optional

from ai.layer1_authenticity import MelCNN


class GradCAMGenerator:
    """
    Gradient-weighted Class Activation Mapping for the MelCNN branch.

    How it works:
      1. Forward pass through CNN features — capture activations at the last conv layer
      2. Backward pass — compute gradients of the output w.r.t. those activations
      3. Weight each activation channel by its mean gradient (importance)
      4. Sum weighted activations → ReLU → normalize → overlay on spectrogram
    """

    def __init__(self, cnn_model: MelCNN, target_layer_index: int = -1):
        """
        Args:
            cnn_model: The MelCNN model instance
            target_layer_index: Which conv block to hook into.
                                -1 = last block (default, highest-level features).
        """
        self.model = cnn_model
        self.activations: Optional[torch.Tensor] = None
        self.gradients: Optional[torch.Tensor] = None

        # Register hooks on the target layer within self.model.features
        # Find the last Conv2d layer for the hook
        conv_layers = []
        for i, module in enumerate(self.model.features):
            if isinstance(module, torch.nn.Conv2d):
                conv_layers.append((i, module))

        if not conv_layers:
            raise ValueError("No Conv2d layers found in MelCNN.features")

        target_idx, target_module = conv_layers[target_layer_index]
        target_module.register_forward_hook(self._forward_hook)
        target_module.register_full_backward_hook(self._backward_hook)

    def _forward_hook(self, module, input, output):
        """Capture activations during forward pass."""
        self.activations = output.detach()

    def _backward_hook(self, module, grad_input, grad_output):
        """Capture gradients during backward pass."""
        self.gradients = grad_output[0].detach()

    def _compute_cam(self, mel_input: torch.Tensor) -> np.ndarray:
        """
        Compute the raw Grad-CAM heatmap.
        Returns: 2D numpy array (height, width) normalized to [0, 1].
        """
        self.model.eval()

        # Ensure tensor is on the same device as the model
        device = next(self.model.parameters()).device
        mel_input = mel_input.to(device).clone().requires_grad_(True)

        # Forward pass
        output = self.model(mel_input)

        # Backward pass (gradient of output w.r.t. activations)
        self.model.zero_grad()
        output.backward(retain_graph=True)

        if self.activations is None or self.gradients is None:
            raise RuntimeError("Hooks did not capture activations/gradients")

        # Global Average Pooling of gradients → channel importance weights
        weights = self.gradients.mean(dim=[2, 3], keepdim=True)  # (1, C, 1, 1)

        # Weighted combination of activation maps
        cam = (weights * self.activations).sum(dim=1, keepdim=True)  # (1, 1, H, W)
        cam = F.relu(cam)  # Only keep positive contributions

        # Normalize to [0, 1]
        cam = cam.squeeze().cpu().numpy()
        if cam.max() > 0:
            cam = (cam - cam.min()) / (cam.max() - cam.min() + 1e-8)

        return cam

    def generate(
        self,
        mel_spectrogram: torch.Tensor,
        figsize: tuple = (8, 3),
        dpi: int = 120,
        colormap: str = "jet",
        alpha: float = 0.5,
    ) -> str:
        """
        Generate a Grad-CAM heatmap overlay and return as a base64-encoded PNG.

        Args:
            mel_spectrogram: (1, n_mels, time) or (1, 1, n_mels, time) tensor
            figsize: Figure size (width, height)
            dpi: Resolution
            colormap: Matplotlib colormap for the heatmap
            alpha: Opacity of the heatmap overlay

        Returns:
            Base64-encoded PNG string (ready to embed in JSON or HTML).
        """
        # Ensure shape is (1, 1, n_mels, time)
        mel_input = mel_spectrogram.clone()
        if mel_input.dim() == 2:
            mel_input = mel_input.unsqueeze(0).unsqueeze(0)
        elif mel_input.dim() == 3:
            mel_input = mel_input.unsqueeze(1)

        # Compute Grad-CAM
        cam = self._compute_cam(mel_input)

        # Get the original spectrogram for the background
        mel_np = mel_input.squeeze().detach().cpu().numpy()

        # Resize CAM to match spectrogram dimensions
        from scipy.ndimage import zoom as scipy_zoom
        if cam.shape != mel_np.shape:
            zoom_factors = (
                mel_np.shape[0] / cam.shape[0],
                mel_np.shape[1] / cam.shape[1],
            )
            cam_resized = scipy_zoom(cam, zoom_factors, order=1)
        else:
            cam_resized = cam

        # Create the visualization
        fig, ax = plt.subplots(1, 1, figsize=figsize, dpi=dpi)

        # Background: mel spectrogram in grayscale
        ax.imshow(
            mel_np, aspect="auto", origin="lower",
            cmap="gray", interpolation="bilinear"
        )
        # Overlay: Grad-CAM heatmap
        im = ax.imshow(
            cam_resized, aspect="auto", origin="lower",
            cmap=colormap, alpha=alpha, interpolation="bilinear"
        )

        ax.set_xlabel("Time Frame", fontsize=10, color="#666")
        ax.set_ylabel("Mel Frequency Bin", fontsize=10, color="#666")
        ax.set_title("Grad-CAM: Detected Synthesis Artifacts", fontsize=12, fontweight="bold")
        ax.tick_params(colors="#666")

        # Add a colorbar
        cbar = plt.colorbar(im, ax=ax, fraction=0.02, pad=0.04)
        cbar.set_label("Artifact Intensity", fontsize=9, color="#666")
        cbar.ax.tick_params(colors="#666")

        plt.tight_layout()

        # Convert to base64 PNG
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
        plt.close(fig)
        buf.seek(0)

        return base64.b64encode(buf.read()).decode("utf-8")

    def generate_comparison(
        self,
        mel_real: torch.Tensor,
        mel_fake: torch.Tensor,
    ) -> str:
        """
        Generate a side-by-side comparison of Grad-CAM for a real vs fake sample.
        Useful for demo presentations and judge Q&A.

        Returns:
            Base64-encoded PNG string.
        """
        def _prepare(mel):
            if mel.dim() == 2:
                return mel.unsqueeze(0).unsqueeze(0)
            elif mel.dim() == 3:
                return mel.unsqueeze(1)
            return mel

        mel_real_in = _prepare(mel_real.clone())
        mel_fake_in = _prepare(mel_fake.clone())

        cam_real = self._compute_cam(mel_real_in)
        cam_fake = self._compute_cam(mel_fake_in)

        real_np = mel_real_in.squeeze().detach().cpu().numpy()
        fake_np = mel_fake_in.squeeze().detach().cpu().numpy()

        from scipy.ndimage import zoom as scipy_zoom

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 4), dpi=120)

        # Real sample
        ax1.imshow(real_np, aspect="auto", origin="lower", cmap="gray")
        if cam_real.shape != real_np.shape:
            cam_real = scipy_zoom(cam_real, (
                real_np.shape[0] / cam_real.shape[0],
                real_np.shape[1] / cam_real.shape[1]
            ), order=1)
        ax1.imshow(cam_real, aspect="auto", origin="lower", cmap="jet", alpha=0.5)
        ax1.set_title("✅ REAL Voice", fontsize=13, fontweight="bold", color="green")
        ax1.set_xlabel("Time Frame")
        ax1.set_ylabel("Mel Bin")

        # Fake sample
        ax2.imshow(fake_np, aspect="auto", origin="lower", cmap="gray")
        if cam_fake.shape != fake_np.shape:
            cam_fake = scipy_zoom(cam_fake, (
                fake_np.shape[0] / cam_fake.shape[0],
                fake_np.shape[1] / cam_fake.shape[1]
            ), order=1)
        ax2.imshow(cam_fake, aspect="auto", origin="lower", cmap="jet", alpha=0.5)
        ax2.set_title("🚨 FAKE Voice (AI Clone)", fontsize=13, fontweight="bold", color="red")
        ax2.set_xlabel("Time Frame")
        ax2.set_ylabel("Mel Bin")

        plt.suptitle(
            "VoiceShield — Explainable AI: Where Are the Artifacts?",
            fontsize=14, fontweight="bold", y=1.02
        )
        plt.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
        plt.close(fig)
        buf.seek(0)

        return base64.b64encode(buf.read()).decode("utf-8")
