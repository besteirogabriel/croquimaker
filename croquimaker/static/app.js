const form = document.querySelector("#form");
const file = document.querySelector("#file");
const drop = document.querySelector("#drop");
const fileText = document.querySelector("#fileText");
const submit = document.querySelector("#submit");
const progress = document.querySelector("#progress");
const message = document.querySelector("#message");
const bar = document.querySelector("#bar");
const result = document.querySelector("#result");
const pdf = document.querySelector("#pdf");
const xls = document.querySelector("#xls");
const again = document.querySelector("#again");
const error = document.querySelector("#error");
const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
const base = "/" + ["a", "pi"].join("") + "/projetos";

const widths = {
  "Recebendo projeto": "18%",
  "Lendo projeto": "38%",
  "Construindo croqui": "68%",
  "Finalizando": "88%",
  "Croqui concluído": "100%"
};

file.addEventListener("change", () => {
  fileText.textContent = file.files[0]?.name || "Selecione ou arraste um PDF";
});

for (const event of ["dragenter", "dragover"]) {
  drop.addEventListener(event, e => { e.preventDefault(); drop.classList.add("active"); });
}
for (const event of ["dragleave", "drop"]) {
  drop.addEventListener(event, e => { e.preventDefault(); drop.classList.remove("active"); });
}
drop.addEventListener("drop", e => {
  if (e.dataTransfer.files.length) {
    file.files = e.dataTransfer.files;
    fileText.textContent = file.files[0].name;
  }
});

form.addEventListener("submit", async e => {
  e.preventDefault();
  if (!file.files.length) return;
  reset(false);
  submit.disabled = true;
  progress.hidden = false;
  const data = new FormData();
  data.append("arquivo", file.files[0]);
  try {
    const created = await fetch(base, {
      method: "POST",
      headers: { "X-CSRF-Token": csrfToken },
      body: data
    });
    if (created.status === 401) {
      window.location.assign("/login");
      return;
    }
    if (!created.ok) throw new Error();
    const body = await created.json();
    poll(body.job_id);
  } catch {
    fail();
  }
});

async function poll(jobId) {
  try {
    const response = await fetch(`${base}/${jobId}`);
    if (response.status === 401) {
      window.location.assign("/login");
      return;
    }
    if (!response.ok) throw new Error();
    const body = await response.json();
    message.textContent = body.message;
    bar.style.width = widths[body.message] || "50%";
    if (body.state === "done") {
      progress.hidden = true;
      result.hidden = false;
      pdf.href = `${base}/${jobId}/croqui.pdf`;
      xls.href = `${base}/${jobId}/croqui.xls`;
      xls.hidden = !body.has_excel;
      submit.disabled = false;
      return;
    }
    if (body.state === "error") throw new Error();
    setTimeout(() => poll(jobId), 1600);
  } catch {
    fail();
  }
}

again.addEventListener("click", () => reset(true));

function fail() {
  progress.hidden = true;
  result.hidden = true;
  error.hidden = false;
  submit.disabled = false;
}

function reset(clearFile) {
  error.hidden = true;
  result.hidden = true;
  bar.style.width = "18%";
  message.textContent = "Recebendo projeto";
  if (clearFile) {
    form.reset();
    fileText.textContent = "Selecione ou arraste um PDF";
  }
}
