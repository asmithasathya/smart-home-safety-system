/*
 * Copyright (c) 2019 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */

/**
 * @file
 * @brief Model handler for the light switch.
 *
 * Instantiates a Generic OnOff Client model for each button on the devkit, as
 * well as the standard Config and Health Server models. Handles all application
 * behavior related to the models.
 */
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/mesh/proxy.h>
#include <bluetooth/mesh/models.h>
#include <dk_buttons_and_leds.h>
#include <string.h>
#include "model_handler.h"

/* Light switch behavior */

/** Context for a single light switch. */
struct button {
	/** Current light status of the corresponding server. */
	bool status;
	/** Generic OnOff client instance for this switch. */
	struct bt_mesh_onoff_cli client;
};

static void status_handler(struct bt_mesh_onoff_cli *cli,
			   struct bt_mesh_msg_ctx *ctx,
			   const struct bt_mesh_onoff_status *status);

static struct button buttons[] = {
#if DT_NODE_EXISTS(DT_ALIAS(sw0))
	{ .client = BT_MESH_ONOFF_CLI_INIT(&status_handler) },
#endif
#if DT_NODE_EXISTS(DT_ALIAS(sw1))
	{ .client = BT_MESH_ONOFF_CLI_INIT(&status_handler) },
#endif
#if DT_NODE_EXISTS(DT_ALIAS(sw2))
	{ .client = BT_MESH_ONOFF_CLI_INIT(&status_handler) },
#endif
#if DT_NODE_EXISTS(DT_ALIAS(sw3)) && !defined(CONFIG_BT_MESH_LOW_POWER)
	{ .client = BT_MESH_ONOFF_CLI_INIT(&status_handler) },
#endif
};

#define CONTROLLER_CLEAR_PASSWORD "1234"

static bool clear_request_pending;

 // Ensures controller shows only one active mode LED at a time
static void show_mode_led(int index)
{
	for (int j = 0; j < ARRAY_SIZE(buttons); ++j) {
		buttons[j].status = false;
		dk_set_led(j, false);
	}

	if (index >= 0 && index < 3) {
		buttons[index].status = true;
		dk_set_led(index, true);
	}
}

// Match each index with the mode name for logging
static const char *action_name(int index)
{
	switch (index) {
	case 0:
		return "HOME";
	case 1:
		return "AWAY";
	case 2:
		return "NIGHT";
	case 3:
		return "CLEAR ALERT";
	default:
		return "UNKNOWN";
	}
}

static void status_handler(struct bt_mesh_onoff_cli *cli,
			   struct bt_mesh_msg_ctx *ctx,
			   const struct bt_mesh_onoff_status *status)
{
	struct button *button =
		CONTAINER_OF(cli, struct button, client);
	int index = button - &buttons[0];

	// Button status from one mode LED at a time
	if (index < 3 && status->present_on_off) {
		show_mode_led(index);
	} else {
		button->status = status->present_on_off;
		dk_set_led(index, status->present_on_off);
	}

	// Logs the status of the button in UART
	printk("%s response: %s\n", action_name(index),
	       status->present_on_off ? "on" : "off");
}

static struct k_work_delayable clear_feedback_off_work;

static void show_clear_feedback(void)
{
	dk_set_led(3, true);
	k_work_reschedule(&clear_feedback_off_work, K_MSEC(300));
}

static int send_button_action(int index)
{
	struct bt_mesh_onoff_set set = {
		.on_off = (index == 3) ? 0 : 1,
	};
	int err;

	printk("Sending %s\n", action_name(index));

	if (bt_mesh_model_pub_is_unicast(buttons[index].client.model) &&
	    !IS_ENABLED(CONFIG_BT_MESH_LOW_POWER)) {
		err = bt_mesh_onoff_cli_set(&buttons[index].client, NULL, &set, NULL);
	} else {
		err = bt_mesh_onoff_cli_set_unack(&buttons[index].client, NULL, &set);
		if (!err) {
			if (index < 3) {
				show_mode_led(index);
			} else {
				buttons[index].status = false;
				show_clear_feedback();
			}
		}
	}

	if (err) {
		printk("OnOff %d set failed: %d\n", index + 1, err);
	}

	return err;
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

	for (int i = 0; i < ARRAY_SIZE(buttons); ++i) {
		if (!(pressed & changed & BIT(i))) {
			continue;
		}

		if (i == 3) {
			show_clear_feedback();
			clear_request_pending = true;
			printk("CLEAR ALERT requested. Enter password in controller UART to confirm.\n");
			continue;
		}

		if (send_button_action(i)) {
			continue;
		}
	}
}

void controller_handle_uart_password(const char *input)
{
	int err;

	if (!clear_request_pending) {
		printk("Password ignored: press CLEAR ALERT first\n");
		return;
	}

	if (strcmp(input, CONTROLLER_CLEAR_PASSWORD) != 0) {
		printk("Password rejected: alert remains active\n");
		return;
	}

	printk("Password accepted: clearing alert\n");
	err = send_button_action(3);
	if (err) {
		printk("Failed to send confirmed clear alert\n");
		return;
	}

	clear_request_pending = false;
}

// Led 3 sends feedback
static void clear_feedback_off(struct k_work *work)
{
	dk_set_led(3, false);
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
#if DT_NODE_EXISTS(DT_ALIAS(sw0))
		BIT(0),
#endif
#if DT_NODE_EXISTS(DT_ALIAS(sw1))
		BIT(1),
#endif
#if DT_NODE_EXISTS(DT_ALIAS(sw2))
		BIT(2),
#endif
#if DT_NODE_EXISTS(DT_ALIAS(sw3))
		BIT(3),
#endif
	};

	if (attention) {
		dk_set_leds(pattern[idx++ % ARRAY_SIZE(pattern)]);
		k_work_reschedule(&attention_blink_work, K_MSEC(30));
	} else {
		dk_set_leds(DK_NO_LEDS_MSK);
	}
}

static void attention_on(const struct bt_mesh_model *mod)
{
	attention = true;
	k_work_reschedule(&attention_blink_work, K_NO_WAIT);
}

static void attention_off(const struct bt_mesh_model *mod)
{
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
#if DT_NODE_EXISTS(DT_ALIAS(sw0))
	BT_MESH_ELEM(1,
		     BT_MESH_MODEL_LIST(
			     BT_MESH_MODEL_CFG_SRV,
			     BT_MESH_MODEL_HEALTH_SRV(&health_srv, &health_pub),
			     BT_MESH_MODEL_ONOFF_CLI(&buttons[0].client)),
		     BT_MESH_MODEL_NONE),
#endif
#if DT_NODE_EXISTS(DT_ALIAS(sw1))
	BT_MESH_ELEM(2,
		     BT_MESH_MODEL_LIST(
			     BT_MESH_MODEL_ONOFF_CLI(&buttons[1].client)),
		     BT_MESH_MODEL_NONE),
#endif
#if DT_NODE_EXISTS(DT_ALIAS(sw2))
	BT_MESH_ELEM(3,
		     BT_MESH_MODEL_LIST(
			     BT_MESH_MODEL_ONOFF_CLI(&buttons[2].client)),
		     BT_MESH_MODEL_NONE),
#endif
#if DT_NODE_EXISTS(DT_ALIAS(sw3)) && !defined(CONFIG_BT_MESH_LOW_POWER)
	BT_MESH_ELEM(4,
		     BT_MESH_MODEL_LIST(
			     BT_MESH_MODEL_ONOFF_CLI(&buttons[3].client)),
		     BT_MESH_MODEL_NONE),
#endif

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
	k_work_init_delayable(&clear_feedback_off_work, clear_feedback_off);
	printk("Controller UART password confirmation enabled for alert clear\n");

	return &comp;
}
