const state = {
  snapshot: null,
  audioArmed: false,
  alertSoundPlaying: false,
  lastModePlayed: null,
  lastAlertState: false,
};

const refs = {};

document.addEventListener("DOMContentLoaded", () => {
  cacheRefs();
  bindAudioToggle();
  connect();
  startClock();
});

function cacheRefs() {
  const ids = [
    "heroBanner",
    "heroOverline",
    "heroTitle",
    "heroSubline",
    "systemStateLabel",
    "lastEventTime",
    "audioToggle",
    "audioStateBadge",
    "audioOrb",
    "syncBadge",
    "modeBadge",
    "shieldStatus",
    "shieldCaption",
    "actionModeChip",
    "actionAudioChip",
    "incidentPanel",
    "incidentTitle",
    "incidentCopy",
    "incidentLevel",
    "incidentZone",
    "incidentTimestamp",
    "timelineList",
    "timelineBadge",
    "nodeGrid",
    "healthBadge",
    "networkState",
    "alertCount",
    "lastIntrusion",
    "phoneHint",
    "controller-meta",
    "light-meta",
    "alarm-meta",
    "room-controller",
    "room-light",
    "room-alarm",
    "alertAudioIndicator",
    "nightAudioIndicator",
  ];

  ids.forEach((id) => {
    refs[id] = document.getElementById(id);
  });

  refs.alertSound = document.getElementById("alertSound");
  refs.nightSound = document.getElementById("nightSound");
}

function bindAudioToggle() {
  refs.audioToggle.addEventListener("click", async () => {
    state.audioArmed = !state.audioArmed;

    if (state.audioArmed) {
      try {
        refs.alertSound.volume = 0;
        await refs.alertSound.play();
        refs.alertSound.pause();
        refs.alertSound.currentTime = 0;
        refs.alertSound.volume = 1;
        refs.nightSound.volume = 0;
        await refs.nightSound.play();
        refs.nightSound.pause();
        refs.nightSound.currentTime = 0;
        refs.nightSound.volume = 1;
      } catch (_err) {
        state.audioArmed = false;
      }
    } else {
      stopAlertLoop();
    }

    syncAudioUI();

    if (
      state.audioArmed &&
      state.snapshot &&
      state.snapshot.global &&
      state.snapshot.global.alert_active
    ) {
      startAlertLoop();
    }
  });
}

function syncAudioUI() {
  refs.audioToggle.textContent = state.audioArmed ? "Audio Ready" : "Enable Audio";
  refs["audioStateBadge"].textContent = state.audioArmed
    ? "Browser audio armed"
    : "Browser locked";
  refs["actionAudioChip"].textContent = state.audioArmed ? "Audio Ready" : "Audio Locked";
}

async function connect() {
  try {
    const initial = await fetch("/api/state").then((response) => response.json());
    applySnapshot(initial);
  } catch (_error) {
    applySnapshot(mockSnapshot());
  }

  let stream;
  try {
    stream = new EventSource("/events");
  } catch (_error) {
    refs["syncBadge"].textContent = "Offline preview";
    refs["networkState"].textContent = "Demo only";
    return;
  }

  stream.addEventListener("state", (event) => {
    try {
      const payload = JSON.parse(event.data);
      applySnapshot(payload);
    } catch (_error) {}
  });

  stream.onerror = () => {
    refs["syncBadge"].textContent = "Reconnecting…";
    refs["networkState"].textContent = "Stream lost";
  };
}

function applySnapshot(snapshot) {
  state.snapshot = snapshot;

  const theme = snapshot.global.alert_active
    ? "alert"
    : snapshot.global.mode.toLowerCase();
  document.body.dataset.theme = theme;

  refs["heroOverline"].textContent = snapshot.global.alert_active
    ? "Critical alert"
    : "Mesh synchronized";
  refs["heroTitle"].textContent = snapshot.ui.hero_title;
  refs["heroSubline"].textContent = snapshot.ui.hero_subline;
  refs["systemStateLabel"].textContent = snapshot.ui.system_label;
  refs["lastEventTime"].textContent = snapshot.ui.last_event_time;
  refs["modeBadge"].textContent = snapshot.global.mode;
  refs["syncBadge"].textContent = snapshot.ui.sync_label;
  refs["shieldStatus"].textContent = snapshot.ui.shield_title;
  refs["shieldCaption"].textContent = snapshot.ui.shield_subtitle;
  refs["actionModeChip"].textContent = snapshot.global.mode;
  refs["timelineBadge"].textContent = snapshot.global.alert_active ? "Live alert" : "Live";
  refs["incidentTitle"].textContent = snapshot.ui.incident_title;
  refs["incidentCopy"].textContent = snapshot.ui.incident_copy;
  refs["incidentLevel"].textContent = snapshot.ui.incident_level;
  refs["incidentZone"].textContent = `Zone: ${snapshot.ui.incident_zone}`;
  refs["incidentTimestamp"].textContent = `Time: ${snapshot.ui.incident_time}`;
  refs["healthBadge"].textContent = `${snapshot.ui.online_count} / 3 online`;
  refs["networkState"].textContent = snapshot.ui.network_label;
  refs["alertCount"].textContent = String(snapshot.metrics.alert_count);
  refs["lastIntrusion"].textContent = snapshot.metrics.last_intrusion;

  if (snapshot.server_url) {
    refs["phoneHint"].textContent = snapshot.server_url;
  }

  refs["controller-meta"].textContent = describeRoom(snapshot.nodes.controller);
  refs["light-meta"].textContent = describeRoom(snapshot.nodes.light);
  refs["alarm-meta"].textContent = describeRoom(snapshot.nodes.alarm);

  updateRoomClasses(snapshot);
  renderTimeline(snapshot.timeline);
  renderNodes(snapshot.nodes);
  handleAudio(snapshot);
}

function describeRoom(node) {
  const bits = [];
  bits.push(node.online ? "Online" : "Offline");
  bits.push(node.mode);

  if (node.armed !== null) {
    bits.push(node.armed ? "Armed" : "Disarmed");
  }

  if (node.alert_active) {
    bits.push("Alert");
  }

  return bits.join(" • ");
}

function updateRoomClasses(snapshot) {
  [
    ["room-controller", snapshot.nodes.controller],
    ["room-light", snapshot.nodes.light],
    ["room-alarm", snapshot.nodes.alarm],
  ].forEach(([id, node]) => {
    const room = refs[id];
    room.classList.toggle("is-online", node.online);
    room.classList.toggle("is-alert", node.alert_active);
    room.style.opacity = node.online ? "1" : "0.56";
    room.style.filter = node.alert_active ? "drop-shadow(0 0 24px rgba(255,91,83,0.28))" : "none";
  });
}

function renderTimeline(items) {
  refs["timelineList"].innerHTML = items
    .map(
      (item) => `
        <article class="timeline-item ${item.kind}">
          <div class="timeline-item-content">
            <p class="timeline-time">${escapeHtml(item.time_label)}</p>
            <p class="timeline-title">${escapeHtml(item.title)}</p>
            <p class="timeline-detail">${escapeHtml(item.detail)}</p>
          </div>
        </article>
      `
    )
    .join("");
}

function renderNodes(nodes) {
  const order = ["controller", "light", "alarm"];

  refs["nodeGrid"].innerHTML = order
    .map((key) => {
      const node = nodes[key];
      const meter = Math.max(10, Math.min(100, node.signal_percent));
      return `
        <article class="node-card">
          <div>
            <p class="node-title">${escapeHtml(node.display_name)}</p>
            <p class="node-subtitle">${escapeHtml(node.mode)}${
              node.armed !== null ? ` • ${node.armed ? "Armed" : "Disarmed"}` : ""
            }</p>
          </div>
          <div>
            <p class="node-signal">${node.online ? `${node.signal_dbm} dBm` : "No signal"}</p>
            <div class="node-meter"><span style="width:${meter}%"></span></div>
          </div>
          <p class="node-last">${escapeHtml(node.last_seen_label)}</p>
        </article>
      `;
    })
    .join("");
}

function handleAudio(snapshot) {
  const alertActive = snapshot.global.alert_active;
  const currentMode = snapshot.global.mode;

  if (state.audioArmed && alertActive && !state.lastAlertState) {
    startAlertLoop();
  } else if (!alertActive && state.lastAlertState) {
    stopAlertLoop();
  }

  if (
    state.audioArmed &&
    currentMode === "NIGHT" &&
    state.lastModePlayed !== "NIGHT"
  ) {
    refs.nightSound.currentTime = 0;
    refs.nightSound.play().catch(() => {});
    refs["nightAudioIndicator"].textContent = "Triggered";
    setTimeout(() => {
      refs["nightAudioIndicator"].textContent = "Standby";
    }, 2200);
  }

  state.lastModePlayed = currentMode;
  state.lastAlertState = alertActive;
}

function startAlertLoop() {
  refs.alertSound.currentTime = 0;
  refs.alertSound.play().catch(() => {
    refs["alertAudioIndicator"].textContent = "Blocked";
    state.alertSoundPlaying = false;
  });
  state.alertSoundPlaying = true;
  refs["alertAudioIndicator"].textContent = "Playing";

  if ("vibrate" in navigator) {
    navigator.vibrate([160, 80, 160, 80, 240]);
  }
}

function stopAlertLoop() {
  refs.alertSound.pause();
  refs.alertSound.currentTime = 0;
  state.alertSoundPlaying = false;
  refs["alertAudioIndicator"].textContent = "Standby";
}

function startClock() {
  setInterval(() => {
    if (!state.snapshot) {
      return;
    }

    refs["lastEventTime"].textContent = state.snapshot.ui.last_event_time;
  }, 1000);
}

function mockSnapshot() {
  return {
    server_url: "",
    global: { mode: "HOME", alert_active: false },
    metrics: { alert_count: 0, last_intrusion: "None" },
    nodes: {
      controller: mockNode("Entryway Controller", "HOME", false, false, 78, -67),
      light: mockNode("Living Room Light", "HOME", null, false, 82, -52),
      alarm: mockNode("Bedroom Alarm", "HOME", false, false, 74, -41),
    },
    timeline: [
      {
        kind: "info",
        time_label: "Demo",
        title: "Dashboard offline fallback",
        detail: "Launch the Python command center for live UART telemetry.",
      },
    ],
    ui: {
      hero_title: "HOME MODE ENGAGED",
      hero_subline: "Waiting for live UART events from controller, light, and alarm.",
      system_label: "Disarmed Home",
      last_event_time: "Waiting for UART",
      sync_label: "Demo mode",
      shield_title: "HOME SAFE",
      shield_subtitle: "Command center ready for live data",
      incident_title: "No active incident",
      incident_copy: "Waiting for controller, light, and alarm activity.",
      incident_level: "Stable",
      incident_zone: "Apartment",
      incident_time: "--",
      network_label: "Demo only",
      online_count: 3,
    },
  };
}

function mockNode(displayName, mode, armed, alertActive, signalPercent, signalDbm) {
  return {
    display_name: displayName,
    online: true,
    mode,
    armed,
    alert_active: alertActive,
    signal_percent: signalPercent,
    signal_dbm: signalDbm,
    last_seen_label: "Demo source active",
  };
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
