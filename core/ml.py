import os
import time
import logging
from simdat.core import tools

io = tools.MLIO()
dt = tools.DATA()


class Args(object):
    def __init__(self, pfs=['ml.json']):
        """Init function of Args

        Keyword arguments:
        pfs -- profiles to read (default: ['ml.json'])

        """
        self._add_args()
        for f in pfs:
            self._set_args(f)

    def _add_args(self):
        """Called by __init__ of Args class"""
        pass

    def _set_args(self, f):
        """Read parameters from profile

        @param f: profile file

        """

        if not os.path.isfile(f):
            print("WARNING: File %s does not exist" % f)
            return
        inparm = io.parse_json(f)
        cinst = self.__dict__.keys()
        for k in inparm:
            if k in cinst:
                setattr(self, k, inparm[k])


class DataArgs(Args):
    def _add_args(self):
        """Called by __init__ of Args class"""

        self._add_da_args()

    def _add_da_args(self):
        """Add additional arguments for MLData class"""

        self.target = None
        self.start = None
        self.end = None
        self.query_map = None
        self.extend_map = None

        self.target_bin = True
        self.inc_flat = True
        self.label = 'trend'
        self.flat_thre = 0.002
        self.shift = 1
        self.norm = 'l2'
        self.extend_by_shift = True


class MLArgs(Args):
    def _add_args(self):
        """Called by __init__ of Args class"""

        self._add_ml_args()

    def _add_ml_args(self):
        """Add additional arguments for MLRun class"""

        self.njobs = 4
        self.nfolds = 5
        self.test_size = 0.33
        self.random = 42
        self.outd = './'


class SVMArgs(MLArgs):
    def _add_args(self):
        """Function to add additional arguments"""

        self._add_ml_args()
        self._add_svm_args()

    def _add_svm_args(self):
        """Add additional arguments for SVM class"""

        self.kernel = 'rbf'
        self.degree = 3
        self.C = [0.1, 1, 10, 100, 1000]
        self.grids = self._set_grids()
        self._set_grids_C()

    def _set_grids(self):
        """Set SVM grids for GridSearchCV

        @return a dictionary of grid parameters

        """

        grids = [{'kernel': ['rbf'],
                  'gamma': [0.0001, 0.0005, 0.001, 0.005, 0.01, 0.1]},
                 {'kernel': ['linear']},
                 {'kernel': ['poly'],
                  'coef0': [1, 10, 100, 1000],
                  'degree': [1, 2, 3, 4]},
                 {'kernel': ['sigmoid'],
                  'coef0': [1, 10, 100, 1000]}]
        if self.kernel != 'auto':
            for g in grids:
                if g['kernel'][0] == self.kernel:
                    return [g]
        return grids

    def _set_grids_C(self):
        """Set C for grids"""

        from copy import deepcopy
        if type(self.C) is not list:
            self.C = [self.C]
        for i in range(0, len(self.grids)):
            if 'C' not in self.grids[i]:
                self.grids[i]['C'] = deepcopy(self.C)


class MLRun():
    def __init__(self, pfs=['ml.json']):
        """Init function of MLRun class

        Keyword arguments:
        pfs -- profiles to read (default: ['ml.json'])

        """
        self.ml_init(pfs)

    def ml_init(self, pfs):
        """Initialize arguments needed

        @param pfs: profiles to be read (used by MLArgs)

        """
        self.args = MLArgs(pfs=pfs)

    def _run(self, data, target, method='SVC'):
        """Run spliting sample, training and testing

        @param data: Input full data array (multi-dimensional np array)
        @param target: Input full target array (1D np array)

        Keyword arguments:
        method -- machine learning method to be used (default: svm.SVC)

        """
        length = dt.check_len(data, target)
        train_d, test_d, train_t, test_t = \
            self.split_samples(data, target)
        model = self.train_with_grids(train_d, train_t, method)
        if len(test_t) > 0:
            result = self.test(test_d, test_t, model)
        else:
            print('No additional testing is performed')

    def split_samples(self, data, target):
        """Split samples

        @param data: Input full data array (multi-dimensional np array)
        @param target: Input full target array (1D np array)

        """
        from sklearn import cross_validation
        train_d, test_d, train_t, test_t = \
            cross_validation.train_test_split(data, target,
                                              test_size=self.args.test_size,
                                              random_state=self.args.random)
        return train_d, test_d, train_t, test_t

    def train_with_grids(self, data, target, method):
        """Train with GridSearchCV to Find the best parameters

        @param data: Input training data array (multi-dimensional np array)
        @param target: Input training target array (1D np array)
        @param method: machine learning method to be used

        @return clf model trained

        """

        t0 = time.time()
        if 'grids' not in self.args.__dict__.keys():
            raise Exception("grids are not set properly")

        from sklearn import cross_validation
        from sklearn.grid_search import GridSearchCV

        print_len = 50
        logging.debug('Splitting the jobs into %i' % self.args.njobs)
        print('GridSearchCV for: %s' % str(self.args.grids))
        log_level = logging.getLogger().getEffectiveLevel()

        def _verbose_level(log_level):
            return int(log_level * (-0.1) + 3)
        verbose = 0 if log_level == 30 else _verbose_level(log_level)

        cv = cross_validation.KFold(len(data),
                                    n_folds=self.args.nfolds)
        if method == 'SVC':
            from sklearn import svm
            model = svm.SVC()
        else:
            from sklearn import svm
            model = sklearn.svm.SVC()
        clf = GridSearchCV(model, self.args.grids,
                           n_jobs=self.args.njobs,
                           cv=cv, verbose=verbose)

        logging.debug('First %i samples of training data' % print_len)
        logging.debug(str(data[:print_len]))
        logging.debug('First %i samples of training target' % print_len)
        logging.debug(str(target[:print_len]))

        clf.fit(data, target)
        best_parms = clf.best_params_
        t0 = dt.print_time(t0, 'find best parameters - train_with_grids')
        print ('Best parameters are: %s' % str(best_parms))
        self.save_model(method, clf)

        return clf

    def save_model(self, fprefix, model):
        """Save model to a file for future use

        @param fprefix: prefix of the output file
        @param model: model to be saved

        """
        import pickle
        io.dir_check(self.args.outd)
        outf = ''.join([self.args.outd, fprefix, '.pkl'])

        with open(outf, 'w') as f:
            pickle.dump(model, f)
        print("Model is saved to %s" % outf)

    def read_model(self, fmodel):
        """Read model from a file

        @param fmodel: file path of the input model

        """
        if not os.path.isfile(fmodel):
            raise Exception("Model file %s does not exist." % fmodel)

        import pickle
        with open(fmodel, 'r') as f:
            model = pickle.load(f)
        return model

    def predict(self, data, trained_model, outf=None):
        """Predict using the existing model

        @param data: Input testing data array (multi-dimensional np array)
        @param trained_model: pre-trained model used for predicting

        Keyword arguments:
        outf -- path of the output file (default: no output)

        """
        result = {'Result': trained_model.predict(data)}
        if outf is not None:
            io.write_json(result, fname=outf)
        return result

    def test(self, data, target, trained_model):
        """Test the existing model

        @param data: Input testing data array (multi-dimensional np array)
        @param target: Input testing target array (1D np array)
        @param trained_model: pre-trained model used for testing

        @return a dictionary of accuracy, std error and predicted output

        """
        from sklearn import metrics
        print_len = 50
        predicted = trained_model.predict(data)
        accuracy = metrics.accuracy_score(target, predicted)
        error = dt.cal_standard_error(predicted)

        print("Accuracy: %0.5f (+/- %0.5f)" % (accuracy, error))

        result = {'accuracy': accuracy, 'error': error,
                  'predicted': predicted}

        logging.debug('First %i results from the predicted' % print_len)
        logging.debug(str(predicted[:print_len]))
        logging.debug('First %i results from the testing target' % print_len)
        logging.debug(str(target[:print_len]))

        return result


class SVMRun(MLRun):
    def ml_init(self, pfs):
        """Initialize arguments needed

        @param pfs: profiles to be read (used by SVMArgs)

        """
        self.args = SVMArgs(pfs=pfs)

    def run(self, data, target):
        """Run spliting sample, training and testing

        @param data: Input full data array (multi-dimensional np array)
        @param target: Input full target array (1D np array)

        """

        return self._run(data, target, method='SVC')