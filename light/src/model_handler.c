/*
 * Copyright (c) 2019 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */

#include <zephyr/kernel.h>
#include <zephyr/bluetooth/bluetooth.h>
#include <bluetooth/mesh/models.h>
#include <dk_buttons_and_leds.h>
#include "model_handler.h"

#define HOME_LED_MASK BIT(0)
#define AWAY_LED_MASK BIT(1)
#define NIGHT_LED_MASK (BIT(2) | BIT(3))
#define ALL_LED_MASK (BIT(0) | BIT(1) | BIT(2) | BIT(3))
#define ALERT_BLINK_PERIOD_MS 250

enum safety_mode {
	MODE_HOME,
	MODE_AWAY,
	MODE_NIGHT,
};

enum logical_channel {
	CHANNEL_HOME,
	CHANNEL_AWAY,
	CHANNEL_NIGHT,
	CHANNEL_ALERT,
	CHANNEL_COUNT,
};

struct node_state {
	enum safety_mode mode;
	bool alert_active;
};

struct channel_ctx {
	struct bt_mesh_onoff_srv srv;
	enum logical_channel channel;
};

static void channel_set(struct bt_mesh_onoff_srv *srv, struct bt_mesh_msg_ctx *ctx,
			const struct bt_mesh_onoff_set *set,
			struct bt_mesh_onoff_status *rsp);

static void channel_get(struct bt_mesh_onoff_srv *srv, struct bt_mesh_msg_ctx *ctx,
			struct bt_mesh_onoff_status *rsp);

static const struct bt_mesh_onoff_srv_handlers onoff_handlers = {
	.set = channel_set,
	.get = channel_get,
};

static struct node_state state = {
	.mode = MODE_HOME,
	.alert_active = false,
};

static struct channel_ctx channels[CHANNEL_COUNT] = {
	[CHANNEL_HOME] = {
		.srv = BT_MESH_ONOFF_SRV_INIT(&onoff_handlers),
		.channel = CHANNEL_HOME,
	},
	[CHANNEL_AWAY] = {
		.srv = BT_MESH_ONOFF_SRV_INIT(&onoff_handlers),
		.channel = CHANNEL_AWAY,
	},
	[CHANNEL_NIGHT] = {
		.srv = BT_MESH_ONOFF_SRV_INIT(&onoff_handlers),
		.channel = CHANNEL_NIGHT,
	},
	[CHANNEL_ALERT] = {
		.srv = BT_MESH_ONOFF_SRV_INIT(&onoff_handlers),
		.channel = CHANNEL_ALERT,
	},
};

/* Health attention blinking and alert blinking both drive the LEDs, so they
 * need to coordinate with each other.
 */
static struct k_work_delayable attention_blink_work;
static struct k_work_delayable alert_blink_work;
static bool attention;
static bool alert_leds_on;

static const char *mode_name(enum safety_mode mode)
{
	switch (mode) {
	case MODE_HOME:
		return "HOME";
	case MODE_AWAY:
		return "AWAY";
	case MODE_NIGHT:
		return "NIGHT";
	default:
		return "UNKNOWN";
	}
}

static uint8_t mode_led_mask(enum safety_mode mode)
{
	switch (mode) {
	case MODE_HOME:
		return HOME_LED_MASK;
	case MODE_AWAY:
		return AWAY_LED_MASK;
	case MODE_NIGHT:
		return NIGHT_LED_MASK;
	default:
		return 0;
	}
}

static bool channel_value(enum logical_channel channel)
{
	switch (channel) {
	case CHANNEL_HOME:
		return state.mode == MODE_HOME;
	case CHANNEL_AWAY:
		return state.mode == MODE_AWAY;
	case CHANNEL_NIGHT:
		return state.mode == MODE_NIGHT;
	case CHANNEL_ALERT:
		return state.alert_active;
	default:
		return false;
	}
}

static void fill_status(enum logical_channel channel, struct bt_mesh_onoff_status *status)
{
	bool value = channel_value(channel);

	status->present_on_off = value;
	status->target_on_off = value;
	status->remaining_time = 0;
}

static void render_mode_display(void)
{
	if (attention || state.alert_active) {
		return;
	}

	dk_set_leds(mode_led_mask(state.mode));
}

static void alert_blink(struct k_work *work)
{
	ARG_UNUSED(work);

	if (attention || !state.alert_active) {
		return;
	}

	alert_leds_on = !alert_leds_on;
	dk_set_leds(alert_leds_on ? ALL_LED_MASK : 0);
	k_work_reschedule(&alert_blink_work, K_MSEC(ALERT_BLINK_PERIOD_MS));
}

static void start_alert_display(void)
{
	if (attention) {
		return;
	}

	alert_leds_on = false;
	k_work_reschedule(&alert_blink_work, K_NO_WAIT);
}

static void stop_alert_display(void)
{
	k_work_cancel_delayable(&alert_blink_work);
	alert_leds_on = false;
	render_mode_display();
}

static void set_mode(enum safety_mode mode)
{
	if (state.mode == mode) {
		return;
	}

	state.mode = mode;
	printk("MODE: %s\n", mode_name(mode));
	render_mode_display();
}

static void set_alert(bool active)
{
	if (state.alert_active == active) {
		return;
	}

	state.alert_active = active;
	printk("ALERT: %s\n", active ? "ACTIVE" : "CLEARED");

	if (active) {
		start_alert_display();
	} else {
		stop_alert_display();
	}
}

static void channel_set(struct bt_mesh_onoff_srv *srv, struct bt_mesh_msg_ctx *ctx,
			const struct bt_mesh_onoff_set *set,
			struct bt_mesh_onoff_status *rsp)
{
	struct channel_ctx *channel = CONTAINER_OF(srv, struct channel_ctx, srv);

	ARG_UNUSED(ctx);

	switch (channel->channel) {
	case CHANNEL_HOME:
		if (set->on_off) {
			set_mode(MODE_HOME);
		}
		break;
	case CHANNEL_AWAY:
		if (set->on_off) {
			set_mode(MODE_AWAY);
		}
		break;
	case CHANNEL_NIGHT:
		if (set->on_off) {
			set_mode(MODE_NIGHT);
		}
		break;
	case CHANNEL_ALERT:
		if (set->on_off) {
			set_alert(true);
		} else if (state.alert_active) {
			set_alert(false);
		}
		break;
	default:
		break;
	}

	if (rsp) {
		fill_status(channel->channel, rsp);
	}
}

static void channel_get(struct bt_mesh_onoff_srv *srv, struct bt_mesh_msg_ctx *ctx,
			struct bt_mesh_onoff_status *rsp)
{
	struct channel_ctx *channel = CONTAINER_OF(srv, struct channel_ctx, srv);

	ARG_UNUSED(ctx);
	fill_status(channel->channel, rsp);
}

static void attention_blink(struct k_work *work)
{
	ARG_UNUSED(work);

	static int idx;
	const uint8_t pattern[] = {
		BIT(0),
		BIT(1),
		BIT(2),
		BIT(3),
	};

	if (attention) {
		dk_set_leds(pattern[idx++ % ARRAY_SIZE(pattern)]);
		k_work_reschedule(&attention_blink_work, K_MSEC(30));
	} else {
		render_mode_display();
	}
}

static void attention_on(const struct bt_mesh_model *mod)
{
	ARG_UNUSED(mod);

	attention = true;
	k_work_cancel_delayable(&alert_blink_work);
	k_work_reschedule(&attention_blink_work, K_NO_WAIT);
}

static void attention_off(const struct bt_mesh_model *mod)
{
	ARG_UNUSED(mod);

	attention = false;

	if (state.alert_active) {
		start_alert_display();
	} else {
		render_mode_display();
	}
}

static const struct bt_mesh_health_srv_cb health_srv_cb = {
	.attn_on = attention_on,
	.attn_off = attention_off,
};

static struct bt_mesh_health_srv health_srv = {
	.cb = &health_srv_cb,
};

BT_MESH_HEALTH_PUB_DEFINE(health_pub, 0);

static struct bt_mesh_elem elements[] = {
	BT_MESH_ELEM(
		1,
		BT_MESH_MODEL_LIST(
			BT_MESH_MODEL_CFG_SRV,
			BT_MESH_MODEL_HEALTH_SRV(&health_srv, &health_pub),
			BT_MESH_MODEL_ONOFF_SRV(&channels[CHANNEL_HOME].srv)),
		BT_MESH_MODEL_NONE),
	BT_MESH_ELEM(
		2,
		BT_MESH_MODEL_LIST(
			BT_MESH_MODEL_ONOFF_SRV(&channels[CHANNEL_AWAY].srv)),
		BT_MESH_MODEL_NONE),
	BT_MESH_ELEM(
		3,
		BT_MESH_MODEL_LIST(
			BT_MESH_MODEL_ONOFF_SRV(&channels[CHANNEL_NIGHT].srv)),
		BT_MESH_MODEL_NONE),
	BT_MESH_ELEM(
		4,
		BT_MESH_MODEL_LIST(
			BT_MESH_MODEL_ONOFF_SRV(&channels[CHANNEL_ALERT].srv)),
		BT_MESH_MODEL_NONE),
};

static const struct bt_mesh_comp comp = {
	.cid = CONFIG_BT_COMPANY_ID,
	.elem = elements,
	.elem_count = ARRAY_SIZE(elements),
};

const struct bt_mesh_comp *model_handler_init(void)
{
	k_work_init_delayable(&attention_blink_work, attention_blink);
	k_work_init_delayable(&alert_blink_work, alert_blink);

	dk_set_leds(mode_led_mask(state.mode));
	printk("MODE: %s\n", mode_name(state.mode));
	printk("ALERT: CLEARED\n");

	return &comp;
}
