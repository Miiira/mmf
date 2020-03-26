# Copyright (c) Facebook, Inc. and its affiliates.
import torch
import warnings

from pythia.utils.configuration import Configuration
from pythia.common.registry import registry
from pythia.utils.general import get_optimizer_parameters


def build_trainer(args, *rest, **kwargs):
    configuration = Configuration(args.config)

    # Update with the config override if passed
    configuration.override_with_cmd_config(args.config_override)

    # Now, update with opts args that were passed
    configuration.override_with_cmd_opts(args.opts)

    # Finally, update with args that were specifically passed
    # as arguments
    configuration.update_with_args(args)
    configuration.freeze()

    # Do set runtime args which can be changed by pythia
    configuration.args = args

    config = configuration.get_config()
    registry.register("config", config)
    registry.register("configuration", configuration)

    trainer_type = config.training_parameters.trainer
    trainer_cls = registry.get_trainer_class(trainer_type)
    trainer_obj = trainer_cls(configuration)

    # Set args as an attribute for future use
    setattr(trainer_obj, "args", args)

    return trainer_obj


def build_model(config):
    model_name = config.model

    model_class = registry.get_model_class(model_name)

    if model_class is None:
        registry.get("writer").write("No model registered for name: %s" % model_name)
    model = model_class(config)

    if hasattr(model, "build"):
        model.build()
        model.init_losses_and_metrics()

    return model


def build_optimizer(model, config):
    optimizer_config = config.optimizer_attributes
    if not hasattr(optimizer_config, "type"):
        raise ValueError(
            "Optimizer attributes must have a 'type' key "
            "specifying the type of optimizer. "
            "(Custom or PyTorch)"
        )
    optimizer_type = optimizer_config.type

    if not hasattr(optimizer_config, "params"):
        warnings.warn(
            "optimizer attributes has no params defined, defaulting to {}."
        )

    params = getattr(optimizer_config, "params", {})

    if hasattr(torch.optim, optimizer_type):
        optimizer_class = getattr(torch.optim, optimizer_type)
    else:
        optimizer_class = registry.get_optimizer_class(optimizer_type)
        if optimizer_class is None:
            raise ValueError(
                "No optimizer class of type {} present in "
                "either torch or registered to registry"
            )

    parameters = get_optimizer_parameters(model, config)
    optimizer = optimizer_class(parameters, **params)
    return optimizer


def build_scheduler(optimizer, config):
    scheduler_config = config.get("scheduler_attributes", {})

    if not hasattr(scheduler_config, "type"):
        warnings.warn(
            "No type for scheduler specified even though lr_scheduler is True, "
            "setting default to 'Pythia'"
        )
    scheduler_type = getattr(scheduler_config, "type", "pythia")

    if not hasattr(scheduler_config, "params"):
        warnings.warn(
            "scheduler attributes has no params defined, defaulting to {}."
        )
    params = getattr(scheduler_config, "params", {})
    scheduler_class = registry.get_scheduler_class(scheduler_type)
    scheduler = scheduler_class(optimizer, **params)

    return scheduler
