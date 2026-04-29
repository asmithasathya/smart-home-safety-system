/*
 * Copyright (c) 2019 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */

#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/mesh/proxy.h>
#include <bluetooth/mesh/models.h>
#include <dk_buttons_and_leds.h>
#include "model_handler.h"

enum safety_mode {
	SAFETY_MODE_HOME,
	SAFETY_MODE_AWAY,
	SAFETY_MODE_NIGHT,
};

enum logical_channel {
	CHANNEL_HOME = 0,
	CHANNEL_AWAY = 1,
	CHANNEL_NIGHT = 2,
	CHANNEL_ALERT = 3,
	CHANNEL_COUNT = 4,
};

struct node_state {
	enum safety_mode mode;
	bool armed;
	bool alert_active;
};

struct channel_srv {
	struct bt_mesh_onoff_srv srv;
	enum logical_channel channel;
};

static void server_set(struct bt_mesh_onoff_srv *srv, struct bt_mesh_msg_ctx *ctx,
		       const struct bt_mesh_onoff_set *set,
		       struct bt_mesh_onoff_status *rsp);
static void server_get(struct bt_mesh_onoff_srv *srv, struct bt_mesh_msg_ctx *ctx,
		       struct bt_mesh_onoff_status *rsp);

static const struct bt_mesh_onoff_srv_handlers onoff_handlers = {
	.set = server_set,
	.get = server_get,
};

static struct channel_srv servers[CHANNEL_COUNT] = {
	{ .srv = BT_MESH_ONOFF_SRV_INIT(&onoff_handlers), .channel = CHANNEL_HOME },
	{ .srv = BT_MESH_ONOFF_SRV_INIT(&onoff_handlers), .channel = CHANNEL_AWAY },
	{ .srv = BT_MESH_ONOFF_SRV_INIT(&onoff_handlers), .channel = CHANNEL_NIGHT },
	{ .srv = BT_MESH_ONOFF_SRV_INIT(&onoff_handlers), .channel = CHANNEL_ALERT },
};

static void alert_status_handler(struct bt_mesh_onoff_cli *cli,
				 struct bt_mesh_msg_ctx *ctx,
				 const struct bt_mesh_onoff_status *status)
{
	ARG_UNUSED(cli);
	ARG_UNUSED(ctx);
	printk("Alert publish status: %s\n",
	       status->present_on_off ? "ON" : "OFF");
}

static struct bt_mesh_onoff_cli alert_client =
	BT_MESH_ONOFF_CLI_INIT(&alert_status_handler);

static struct node_state state = {
	.mode = SAFETY_MODE_HOME,
	.armed = false,
	.alert_active = false,
};

static struct k_work_delayable alert_blink_work;
static bool alert_leds_on;

static const char *mode_to_str(enum safety_mode mode)
{
	switch (mode) {
	case SAFETY_MODE_HOME:
		return "HOME";
	case SAFETY_MODE_AWAY:
		return "AWAY";
	case SAFETY_MODE_NIGHT:
		return "NIGHT";
	default:
		return "UNKNOWN";
	}
}

static void show_mode_pattern(void)
{
	switch (state.mode) {
	case SAFETY_MODE_HOME:
		dk_set_leds(BIT(0));
		break;
	case SAFETY_MODE_AWAY:
		dk_set_leds(BIT(1));
		break;
	case SAFETY_MODE_NIGHT:
		dk_set_leds(BIT(2) | BIT(3));
		break;
	}
}

static void apply_display_state(void)
{
	if (state.alert_active) {
		k_work_reschedule(&alert_blink_work, K_NO_WAIT);
		return;
	}

	k_work_cancel_delayable(&alert_blink_work);
	alert_leds_on = false;
	show_mode_pattern();
}

static void print_mode_and_alert(void)
{
	printk("MODE: %s (%s)\n", mode_to_str(state.mode),
	       state.armed ? "armed" : "disarmed");
	printk("ALERT: %s\n", state.alert_active ? "ACTIVE" : "CLEAR");
}

static void set_mode(enum safety_mode mode)
{
	state.mode = mode;
	state.armed = (mode != SAFETY_MODE_HOME);
	print_mode_and_alert();
	apply_display_state();
}

static void set_alert(bool active)
{
	state.alert_active = active;
	print_mode_and_alert();
	apply_display_state();
}

static uint8_t present_onoff_for_channel(enum logical_channel channel)
{
	switch (channel) {
	case CHANNEL_HOME:
		return state.mode == SAFETY_MODE_HOME;
	case CHANNEL_AWAY:
		return state.mode == SAFETY_MODE_AWAY;
	case CHANNEL_NIGHT:
		return state.mode == SAFETY_MODE_NIGHT;
	case CHANNEL_ALERT:
		return state.alert_active;
	default:
		return 0;
	}
}

static void populate_status(enum logical_channel channel,
			    struct bt_mesh_onoff_status *rsp)
{
	rsp->present_on_off = present_onoff_for_channel(channel);
	rsp->target_on_off = rsp->present_on_off;
	rsp->remaining_time = 0;
}

static void server_set(struct bt_mesh_onoff_srv *srv, struct bt_mesh_msg_ctx *ctx,
		       const struct bt_mesh_onoff_set *set,
		       struct bt_mesh_onoff_status *rsp)
{
	struct channel_srv *channel_srv =
		CONTAINER_OF(srv, struct channel_srv, srv);

	ARG_UNUSED(ctx);

	switch (channel_srv->channel) {
	case CHANNEL_HOME:
		if (set->on_off) {
			set_mode(SAFETY_MODE_HOME);
		}
		break;
	case CHANNEL_AWAY:
		if (set->on_off) {
			set_mode(SAFETY_MODE_AWAY);
		}
		break;
	case CHANNEL_NIGHT:
		if (set->on_off) {
			set_mode(SAFETY_MODE_NIGHT);
		}
		break;
	case CHANNEL_ALERT:
		set_alert(set->on_off);
		break;
	default:
		break;
	}

	if (rsp) {
		populate_status(channel_srv->channel, rsp);
	}
}

static void server_get(struct bt_mesh_onoff_srv *srv, struct bt_mesh_msg_ctx *ctx,
		       struct bt_mesh_onoff_status *rsp)
{
	struct channel_srv *channel_srv =
		CONTAINER_OF(srv, struct channel_srv, srv);

	ARG_UNUSED(ctx);
	populate_status(channel_srv->channel, rsp);
}

static void alert_blink(struct k_work *work)
{
	ARG_UNUSED(work);

	if (!state.alert_active) {
		dk_set_leds(DK_NO_LEDS_MSK);
		return;
	}

	alert_leds_on = !alert_leds_on;
	dk_set_leds(alert_leds_on ? DK_ALL_LEDS_MSK : DK_NO_LEDS_MSK);
	k_work_reschedule(&alert_blink_work, K_MSEC(250));
}

static void publish_alert_on(void)
{
	struct bt_mesh_onoff_set set = {
		.on_off = 1,
	};
	int err;

	if (bt_mesh_model_pub_is_unicast(alert_client.model)) {
		err = bt_mesh_onoff_cli_set(&alert_client, NULL, &set, NULL);
	} else {
		err = bt_mesh_onoff_cli_set_unack(&alert_client, NULL, &set);
	}

	if (err) {
		printk("Failed to publish ALERT ON: %d\n", err);
	}
}

static void button_handler_cb(uint32_t pressed, uint32_t changed)
{
	if (!bt_mesh_is_provisioned()) {
		return;
	}

	if (IS_ENABLED(CONFIG_BT_MESH_LOW_POWER) && (pressed & changed & BIT(3))) {
		bt_mesh_proxy_identity_enable();
		return;
	}

	if (!(pressed & changed & BIT(0))) {
		return;
	}

	if (!state.armed) {
		printk("INTRUSION: IGNORED (DISARMED)\n");
		return;
	}

	printk("INTRUSION: DETECTED (ARMED)\n");
	set_alert(true);
	publish_alert_on();
}

/* Set up a repeating delayed work to blink the DK's LEDs when attention is
 * requested.
 */
static struct k_work_delayable attention_blink_work;
static bool attention;

static void attention_blink(struct k_work *work)
{
	static int idx;
	const uint8_t pattern[] = {
#if DT_NODE_EXISTS(DT_ALIAS(led0))
		BIT(0),
#endif
#if DT_NODE_EXISTS(DT_ALIAS(led1))
		BIT(1),
#endif
#if DT_NODE_EXISTS(DT_ALIAS(led2))
		BIT(2),
#endif
#if DT_NODE_EXISTS(DT_ALIAS(led3))
		BIT(3),
#endif
	};

	ARG_UNUSED(work);

	if (attention) {
		dk_set_leds(pattern[idx++ % ARRAY_SIZE(pattern)]);
		k_work_reschedule(&attention_blink_work, K_MSEC(30));
	} else {
		apply_display_state();
	}
}

static void attention_on(const struct bt_mesh_model *mod)
{
	ARG_UNUSED(mod);
	attention = true;
	k_work_reschedule(&attention_blink_work, K_NO_WAIT);
}

static void attention_off(const struct bt_mesh_model *mod)
{
	ARG_UNUSED(mod);
	/* Will stop rescheduling blink timer */
	attention = false;
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
		1, BT_MESH_MODEL_LIST(
			   BT_MESH_MODEL_CFG_SRV,
			   BT_MESH_MODEL_HEALTH_SRV(&health_srv, &health_pub),
			   BT_MESH_MODEL_ONOFF_SRV(&servers[CHANNEL_HOME].srv),
			   BT_MESH_MODEL_ONOFF_CLI(&alert_client)),
		BT_MESH_MODEL_NONE),
	BT_MESH_ELEM(
		2,
		BT_MESH_MODEL_LIST(BT_MESH_MODEL_ONOFF_SRV(
			&servers[CHANNEL_AWAY].srv)),
		BT_MESH_MODEL_NONE),
	BT_MESH_ELEM(
		3,
		BT_MESH_MODEL_LIST(BT_MESH_MODEL_ONOFF_SRV(
			&servers[CHANNEL_NIGHT].srv)),
		BT_MESH_MODEL_NONE),
	BT_MESH_ELEM(
		4,
		BT_MESH_MODEL_LIST(BT_MESH_MODEL_ONOFF_SRV(
			&servers[CHANNEL_ALERT].srv)),
		BT_MESH_MODEL_NONE),
};

static const struct bt_mesh_comp comp = {
	.cid = CONFIG_BT_COMPANY_ID,
	.elem = elements,
	.elem_count = ARRAY_SIZE(elements),
};

const struct bt_mesh_comp *model_handler_init(void)
{
	static struct button_handler button_handler = {
		.cb = button_handler_cb,
	};

	dk_button_handler_add(&button_handler);
	k_work_init_delayable(&attention_blink_work, attention_blink);
	k_work_init_delayable(&alert_blink_work, alert_blink);

	print_mode_and_alert();
	apply_display_state();

	return &comp;
}
