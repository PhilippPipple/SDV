"""Wrappers around copulas models."""
import warnings
from copy import deepcopy

import copulas
import copulas.multivariate
import copulas.univariate
from rdt.transformers import OneHotEncoder

from sdv.single_table.base import BaseSingleTableSynthesizer


class GaussianCopulaSynthesizer(BaseSingleTableSynthesizer):
    """Model wrapping ``copulas.multivariate.GaussianMultivariate`` copula.

    Args:
        metadata (sdv.metadata.SingleTableMetadata):
            Single table metadata representing the data that this synthesizer will be used for.
        enforce_min_max_values (bool):
            Specify whether or not to clip the data returned by ``reverse_transform`` of
            the numerical transformer, ``FloatFormatter``, to the min and max values seen
            during ``fit``. Defaults to ``True``.
        enforce_rounding (bool):
            Define rounding scheme for ``numerical`` columns. If ``True``, the data returned
            by ``reverse_transform`` will be rounded as in the original data. Defaults to ``True``.
        numerical_distributions (dict):
            Dictionary that maps field names from the table that is being modeled with
            the distribution that needs to be used. The distributions can be passed as either
            a ``copulas.univariate`` instance or as one of the following values:

                * ``norm``: Use a norm distribution.
                * ``beta``: Use a Beta distribution.
                * ``truncnorm``: Use a truncnorm distribution.
                * ``uniform``: Use a uniform distribution.
                * ``gamma``: Use a Gamma distribution.
                * ``gaussian_kde``: Use a GaussianKDE distribution. This model is non-parametric,
                  so using this will make ``get_parameters`` unusable.

        default_distribution (copulas.univariate.Univariate or str):
            Copulas univariate distribution to use by default. Valid options are:

                * ``norm``: Use a norm distribution.
                * ``beta``: Use a Beta distribution.
                * ``truncnorm``: Use a Truncated Gaussian distribution.
                * ``uniform``: Use a uniform distribution.
                * ``gamma``: Use a Gamma distribution.
                * ``gaussian_kde``: Use a GaussianKDE distribution. This model is non-parametric,
                  so using this will make ``get_parameters`` unusable.
             Defaults to ``beta``.
    """

    _DISTRIBUTIONS = {
        'norm': copulas.univariate.GaussianUnivariate,
        'beta': copulas.univariate.BetaUnivariate,
        'truncnorm': copulas.univariate.TruncatedGaussian,
        'gamma': copulas.univariate.GammaUnivariate,
        'uniform': copulas.univariate.UniformUnivariate,
        'gaussian_kde': copulas.univariate.GaussianKDE,
    }

    _model = None

    @classmethod
    def _validate_distribution(cls, distribution):
        if not isinstance(distribution, str) or distribution not in cls._DISTRIBUTIONS:
            error_message = f"Invalid distribution specification '{distribution}'."
            raise ValueError(error_message)

        return cls._DISTRIBUTIONS[distribution]

    def __init__(self, metadata, enforce_min_max_values=True, enforce_rounding=True,
                 numerical_distributions=None, default_distribution=None):
        super().__init__(
            metadata,
            enforce_min_max_values=enforce_min_max_values,
            enforce_rounding=enforce_rounding,
        )
        if numerical_distributions and not isinstance(numerical_distributions, dict):
            raise TypeError('numerical_distributions can only be None or a dict instance')

        self.default_distribution = default_distribution or 'beta'
        self.numerical_distributions = numerical_distributions or {}

        self._default_distribution = self._validate_distribution(self.default_distribution)
        self._numerical_distributions = {
            field: self._validate_distribution(distribution)
            for field, distribution in (numerical_distributions or {}).items()
        }

    def _fit(self, processed_data):
        """Fit the model to the table.

        Args:
            processed_data (pandas.DataFrame):
                Data to be learned.
        """
        numerical_distributions = deepcopy(self._numerical_distributions)

        for column in processed_data.columns:
            if column not in numerical_distributions:
                column_name = column.replace('.value', '')
                numerical_distributions[column] = self._numerical_distributions.get(
                    column_name, self._default_distribution)

        self._model = copulas.multivariate.GaussianMultivariate(
            distribution=numerical_distributions
        )

        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', module='scipy')
            self._model.fit(processed_data)

    def _warn_for_update_transformers(self, column_name_to_transformer):
        """Raise warnings for update_transformers.

        Args:
            column_name_to_transformer (dict):
                Dict mapping column names to transformers to be used for that column.
        """
        for column, transformer in column_name_to_transformer.items():
            sdtype = self.metadata._columns[column]['sdtype']
            if sdtype == 'categorical' and isinstance(transformer, OneHotEncoder):
                warnings.warn(
                    f"Using a OneHotEncoder transformer for column '{column}' "
                    'may slow down the preprocessing and modeling times.'
                )

    def _sample(self, num_rows, conditions=None):
        """Sample the indicated number of rows from the model.

        Args:
            num_rows (int):
                Amount of rows to sample.
            conditions (dict):
                If specified, this dictionary maps column names to the column
                value. Then, this method generates ``num_rows`` samples, all of
                which are conditioned on the given variables.

        Returns:
            pandas.DataFrame:
                Sampled data.
        """
        return self._model.sample(num_rows, conditions=conditions)

    def get_learned_distributions(self):
        """Get the marginal distributions used by the ``GaussianCopula``.

        Return a dictionary mapping the column names with the distribution name and the learned
        parameters for those.

        Returns:
            dict:
                Dictionary containing the distributions used or detected for each column and the
                learned parameters for those.
        """
        if not self._fitted:
            raise ValueError(
                "Distributions have not been learned yet. Please fit your model first using 'fit'")

        parameters = self._model.to_dict()
        columns = parameters['columns']
        univariates = deepcopy(parameters['univariates'])
        learned_distributions = {}
        for column, learned_params in zip(columns, univariates):
            distribution = self.numerical_distributions.get(column, self.default_distribution)
            learned_distributions[column] = {
                'distribution': distribution,
                'learned_parameters': learned_params
            }

        return learned_distributions
