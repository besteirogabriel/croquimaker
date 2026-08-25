(() => {
  const canvas = document.querySelector("#croquiCanvas");
  if (!canvas) return;

  const applyOfficialVectorStyle = () => {
    canvas.querySelectorAll(".scene-symbol path").forEach(path => {
      const fill = path.getAttribute("fill") || "none";
      const stroke = path.getAttribute("stroke") || "none";
      const width = path.getAttribute("stroke-width");
      path.style.fill = fill;
      path.style.stroke = stroke;
      if (width) path.style.strokeWidth = width;
    });
  };

  new MutationObserver(applyOfficialVectorStyle).observe(canvas, {
    childList: true,
    subtree: true,
  });
  applyOfficialVectorStyle();
})();
